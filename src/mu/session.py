"""Performance element (writer loop) and critic (repair loop).

In AIMA terms ``Session.run`` is the **performance element** — it executes the
plan by driving the LLM through the Write/Edit tool loop. ``Session.repair_loop``
is the **critic's execution arm** — it runs the test gate after each model edit
and loops until the performance standard (tests exit 0) is met or the iteration
budget is exhausted. The repair loop returns ``(passed, iters)`` so the caller
can accumulate repair iterations into the session's ``Utility`` record.

``REPAIR_ESCALATE`` is the sentinel ``iters`` value returned when the loop detects
the same distilled error persisting for ``_FOCUS_LOOP_THRESHOLD`` consecutive
passes with no change — a signal that the current plan is structurally stuck and
the caller should escalate (e.g. to architect mode).
"""

REPAIR_ESCALATE: int = -2
_FOCUS_LOOP_THRESHOLD: int = 2  # same FOCUS ≥ this many consecutive passes → escalate
_REPAIR_HISTORY_WINDOW: int = 3  # complete iteration-units to retain in the repair prompt

import difflib
import hashlib
import time
from pathlib import Path
from typing import Callable, Optional

from mu.reflexes import fix_requirements_path_entries

from mu import tools
from mu.client import chat_or_retry
from mu.degeneration import guard_enabled, is_degenerate, note_refusal
from mu.diagnose import distill_test_errors


def _compute_edit_diff(before: str, after: str, path: str, max_chars: int = 1500) -> str:
    """Return a capped unified diff; falls back to a summary line if the diff is too large."""
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    chunks = list(difflib.unified_diff(
        before_lines, after_lines,
        fromfile=f'a/{Path(path).name}', tofile=f'b/{Path(path).name}',
    ))
    if not chunks:
        return ''
    diff_text = ''.join(chunks)
    if len(diff_text) > max_chars:
        return (f"Last edit: rewrote {Path(path).name} "
                f"({len(before_lines)}→{len(after_lines)} lines; diff too large to show)")
    return f"Last edit diff:\n```diff\n{diff_text}```"


def _apply_repair_tool_call(
    tc: dict,
    seen_states: dict,
    consecutive_dups: dict,
    msgs: list,
    syntax_check,
    diffs: Optional[list] = None,
) -> bool:
    """Execute one repair-loop tool call and append the result to *msgs*.

    Handles three safety checks around the dispatch:
    1. **Snapshot + revert** — if *syntax_check* is provided and the edit
       introduces a syntax error, the file is restored to its pre-edit state.
    2. **Duplicate detection** — if the file ends up in a state seen before,
       a DUPLICATE warning is injected so the model tries something different.
    3. **requirements.txt reflex** — path-style entries are stripped after a
       Write to ``requirements.txt``.

    Returns ``True`` when the agent is stuck (same broken state twice in a row),
    signalling the caller to abort the repair loop.
    """
    tools.log_call(tc)
    fn = tc['function']
    name, raw_args = fn['name'], fn['arguments']
    path = tools._as_dict(raw_args).get('path', '')

    before_text: Optional[str] = None
    if name in ('Write', 'Edit') and path and Path(path).exists():
        try:
            before_text = Path(path).read_text()
        except OSError:
            pass

    snapshot: Optional[str] = before_text
    ok_before = True
    if syntax_check and before_text is not None:
        ok_before, _ = syntax_check(path)

    # Record the pre-dispatch digest for duplicate-edit detection.
    if before_text is not None:
        seen_states.setdefault(path, set()).add(
            hashlib.sha1(before_text.encode()).hexdigest())

    result = tools.dispatch(name, raw_args)

    if name == 'Write' and path and path.endswith('requirements.txt'):
        if fix_requirements_path_entries(path):
            result += "\nNOTE: path-style entries removed from requirements.txt"

    # Duplicate-edit check: warn the model if the file is back to a prior state.
    stuck = False
    if name in ('Write', 'Edit') and path and Path(path).exists():
        try:
            digest = hashlib.sha1(Path(path).read_bytes()).hexdigest()
            if digest in seen_states.get(path, set()):
                result += (f"\nDUPLICATE: {path} is now identical to a state you "
                           f"already tried. This edit did not help before — make a "
                           f"different change.")
                print(f"==> [mu-agent] Repair: duplicate edit detected for {path}")
                consecutive_dups[path] = consecutive_dups.get(path, 0) + 1
                if consecutive_dups[path] >= 2:
                    print(f"==> [mu-agent] Repair: stuck on {path} — aborting repair loop.")
                    stuck = True
            else:
                consecutive_dups[path] = 0
                seen_states.setdefault(path, set()).add(digest)
        except OSError:
            pass

    # Revert if the edit introduced a syntax error.
    if syntax_check and snapshot is not None and ok_before and path:
        ok_after, serr = syntax_check(path)
        if not ok_after:
            try:
                Path(path).write_text(snapshot)
                print(f"==> [mu-agent] Repair: reverted syntax-breaking edit to {path}")
                result = (f"{result}\nREVERTED: that edit left {path} with a syntax "
                          f"error, so it was undone. Make a different, complete edit "
                          f"that keeps the file valid. Error:\n{serr}")
            except OSError:
                pass

    msgs.append({'role': 'tool', 'content': result, 'tool_call_id': tc.get('id', '')})

    if diffs is not None and before_text is not None:
        try:
            after_text = Path(path).read_text() if Path(path).exists() else ''
            diff_str = _compute_edit_diff(before_text, after_text, path)
            if diff_str:
                diffs.append(diff_str)
        except OSError:
            pass

    return stuck


class Session:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.tool_set: Optional[list[dict]] = None
        self.watch_func: Optional[Callable[[], bool]] = None

    def run(self, model: str, user_prompt: str, label: str, max_turns: int,
            watch_file: str, timeout: float) -> tuple[bool, Optional[str]]:
        msgs: list[dict] = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': user_prompt},
        ]
        print(f"  {label}...")
        deadline = time.time() + timeout
        tool_defs = self.tool_set if self.tool_set is not None else tools.ALL

        for turn in range(max_turns):
            if time.time() >= deadline:
                return False, f"timeout after {timeout:.0f}s"
            try:
                # Force a tool call: the writer's whole job is to emit one Write,
                # so 'required' stops small models from spending turns on prose.
                msg, _ = chat_or_retry(model, msgs, tool_defs, deadline,
                                       tool_choice='required')
            except Exception as e:
                return False, f"chat: {e}"
            msgs.append(msg)

            if not msg.get('tool_calls'):
                if watch_file:
                    if Path(watch_file).exists():
                        return True, None
                    code, ok = tools.extract_code_block(msg['content'], watch_file)
                    if ok and code and guard_enabled() and is_degenerate(code):
                        # Repetition loop in the extracted block — don't commit a
                        # corrupt file; fall through to resample (CHALLENGES.md #1).
                        note_refusal()
                        print("==> [mu-agent] Degeneration guard: discarded a "
                              "repetition-loop code block; resampling.")
                        ok = False
                    if ok and code:
                        try:
                            Path(watch_file).parent.mkdir(parents=True, exist_ok=True)
                            Path(watch_file).write_text(code)
                            return True, None
                        except OSError:
                            pass
                    # Fall through: nudge the model to call the tool instead of giving up.
                if turn < max_turns - 1:
                    msgs.append({'role': 'user',
                                 'content': 'Call Write or Edit now. Do not write text — call the tool immediately.'})
                    continue
                return False, "max turns reached without tool call"

            for tc in msg['tool_calls']:
                tools.log_call(tc)
                result = tools.dispatch(tc['function']['name'], tc['function']['arguments'])
                msgs.append({'role': 'tool', 'content': result,
                             'tool_call_id': tc.get('id', '')})
                if watch_file and Path(watch_file).exists():
                    return True, None
                if self.watch_func and self.watch_func():
                    return True, None

        if watch_file:
            return Path(watch_file).exists(), "max turns reached"
        return False, "max turns reached"

    def repair_loop(self, model: str, goal: str, max_iters: int,
                    per_turn_timeout: float,
                    run_test: Callable[[], tuple[bool, str]],
                    reapply: Optional[Callable[[], None]],
                    context: str = '',
                    syntax_check: Optional[Callable[[str], tuple[bool, str]]] = None,
                    make_context: Optional[Callable[[str], str]] = None,
                    ) -> tuple[bool, int]:
        tool_defs = self.tool_set if self.tool_set is not None else tools.REPAIR
        system_msg: dict = {'role': 'system', 'content': self.system_prompt}
        all_turns: list[list[dict]] = []  # complete per-iteration units; windowed to last N
        seen_states: dict[str, set[str]] = {}
        consecutive_dups: dict[str, int] = {}
        stuck = False
        _prev_focus: Optional[str] = None
        _same_focus_count: int = 0
        last_diffs: list[str] = []
        print("  Repairing...")

        for i in range(max_iters):
            if reapply:
                reapply()
            passed, test_out = run_test()
            if passed:
                if i > 0:
                    print(f"==> [mu-agent] Repair: tests pass after {i} edit(s).")
                return True, i

            # Lead with a deterministic FOCUS hint: the test output is often
            # dominated by build/pip noise with the real error near the bottom,
            # and a weak model latches onto the wrong line. The distiller names
            # the first actionable error (file, symbol, class) so the model edits
            # the right thing. Empty for unrecognized output — then nothing changes.
            focus = distill_test_errors(test_out)
            focus_block = f"{focus}\n\n" if focus else ''

            # Detect structural stall: same distilled error ≥ threshold consecutive
            # passes with no resolution — the current plan cannot fix this.
            if focus and focus == _prev_focus:
                _same_focus_count += 1
                if _same_focus_count >= _FOCUS_LOOP_THRESHOLD:
                    print(f"==> [mu-agent] Repair stuck: same error for "
                          f"{_same_focus_count + 1} passes — escalating.")
                    return False, REPAIR_ESCALATE
            else:
                _prev_focus = focus
                _same_focus_count = 0

            if i == 0:
                ctx = make_context(test_out) if make_context else context
                content = (f"GOAL: {goal}\n\n{ctx}{focus_block}The project's tests are failing. Make ONE targeted "
                           f"change (call Edit, or Write to replace a whole file) to fix the "
                           f"underlying cause. Do not run any commands — the test is run for you "
                           f"and the new output is shown after each edit. Test output:\n\n{test_out}")
            else:
                fresh_ctx = make_context(test_out) if make_context else ''
                ctx_block = f"{fresh_ctx}\n\n" if fresh_ctx else ''
                diff_block = ('\n\n'.join(last_diffs) + '\n\n') if last_diffs else ''
                content = (f"{ctx_block}{diff_block}{focus_block}Still failing after your last edit. "
                           f"Latest test output:\n\n{test_out}"
                           f"\n\nMake ONE more targeted edit. Do not repeat an edit that did not help.")

            user_msg: dict = {'role': 'user', 'content': content}
            current: list[dict] = [user_msg]
            # Complete units (user→assistant→tool results) keep the tool-call pairing invariant.
            msgs: list[dict] = (
                [system_msg]
                + [m for u in all_turns[-_REPAIR_HISTORY_WINDOW:] for m in u]
                + [user_msg]
            )

            deadline = time.time() + per_turn_timeout
            edited = False
            connection_dead = False
            iter_diffs: list[str] = []
            for t in range(3):
                if time.time() >= deadline:
                    break
                try:
                    # Repair always expects an edit; force the tool call so the
                    # model can't reply with prose ("I would change…") and stall.
                    msg, _ = chat_or_retry(model, msgs, tool_defs, deadline,
                                           tool_choice='required')
                except Exception as e:
                    err = str(e)
                    print(f"==> [mu-agent] Repair: {e}")
                    if any(s in err for s in ('Connection refused', 'Connection reset',
                                              'Server disconnected', 'ConnectionError')):
                        connection_dead = True
                    break
                msgs.append(msg)
                current.append(msg)
                if not msg.get('tool_calls'):
                    if t < 2:
                        nudge = {'role': 'user',
                         'content': 'Call Edit or Write now — do not write prose.'}
                        msgs.append(nudge)
                        current.append(nudge)
                        continue
                    break
                pre = len(msgs)
                for tc in msg['tool_calls']:
                    if _apply_repair_tool_call(tc, seen_states, consecutive_dups,
                                               msgs, syntax_check, iter_diffs):
                        stuck = True
                current.extend(msgs[pre:])
                edited = True
                break

            all_turns.append(current)
            last_diffs = iter_diffs

            if connection_dead:
                print("==> [mu-agent] Repair: connection lost — aborting repair loop.")
                break
            if stuck:
                break
            if not edited:
                print(f"==> [mu-agent] Repair iter {i + 1}: model produced no edit.")

        if reapply:
            reapply()
        passed, _ = run_test()
        return passed, max_iters
