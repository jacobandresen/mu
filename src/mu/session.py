"""Performance element (writer loop) and critic (repair loop).

In AIMA terms ``Session.run`` is the **performance element** — it executes the
plan by driving the LLM through the Write/Edit tool loop. ``Session.repair_loop``
is the **critic's execution arm** — it runs the test gate after each model edit
and loops until the performance standard (tests exit 0) is met or the iteration
budget is exhausted. The repair loop returns ``(passed, iters)`` so the caller
can accumulate repair iterations into the session's ``Utility`` record.
"""

import hashlib
import time
from pathlib import Path
from typing import Callable, Optional

from mu.reflexes import fix_requirements_path_entries

from mu import tools
from mu.client import chat_or_retry


def _apply_repair_tool_call(
    tc: dict,
    seen_states: dict,
    consecutive_dups: dict,
    msgs: list,
    syntax_check,
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

    # Snapshot the file before writing so we can roll back on syntax errors.
    snapshot, ok_before = None, True
    if syntax_check and name in ('Write', 'Edit') and path and Path(path).exists():
        try:
            snapshot = Path(path).read_text()
        except OSError:
            snapshot = None
        ok_before, _ = syntax_check(path)

    # Record the pre-dispatch digest for duplicate-edit detection.
    if name in ('Write', 'Edit') and path and Path(path).exists():
        try:
            seen_states.setdefault(path, set()).add(
                hashlib.sha1(Path(path).read_bytes()).hexdigest())
        except OSError:
            pass

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
                msg, _ = chat_or_retry(model, msgs, tool_defs, deadline)
            except Exception as e:
                return False, f"chat: {e}"
            msgs.append(msg)

            if not msg.get('tool_calls'):
                if watch_file:
                    if Path(watch_file).exists():
                        return True, None
                    code, ok = tools.extract_code_block(msg['content'], watch_file)
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
                    ) -> tuple[bool, int]:
        tool_defs = self.tool_set if self.tool_set is not None else tools.REPAIR
        msgs: list[dict] = [{'role': 'system', 'content': self.system_prompt}]
        seen_states: dict[str, set[str]] = {}  # path -> set of sha1 hashes of seen file contents
        consecutive_dups: dict[str, int] = {}  # path -> consecutive duplicate count
        stuck = False
        print("  Repairing...")

        for i in range(max_iters):
            if reapply:
                reapply()
            passed, test_out = run_test()
            if passed:
                if i > 0:
                    print(f"==> [mu-agent] Repair: tests pass after {i} edit(s).")
                return True, i

            if i == 0:
                content = (f"GOAL: {goal}\n\n{context}The project's tests are failing. Make ONE targeted "
                           f"change (call Edit, or Write to replace a whole file) to fix the "
                           f"underlying cause. Do not run any commands — the test is run for you "
                           f"and the new output is shown after each edit. Test output:\n\n{test_out}")
            else:
                content = (f"Still failing after your last edit. Latest test output:\n\n{test_out}"
                           f"\n\nMake ONE more targeted edit. Do not repeat an edit that did not help.")
            msgs.append({'role': 'user', 'content': content})

            deadline = time.time() + per_turn_timeout
            edited = False
            connection_dead = False
            for t in range(3):
                if time.time() >= deadline:
                    break
                try:
                    msg, _ = chat_or_retry(model, msgs, tool_defs, deadline)
                except Exception as e:
                    err = str(e)
                    print(f"==> [mu-agent] Repair: {e}")
                    if any(s in err for s in ('Connection refused', 'Connection reset',
                                              'Server disconnected', 'ConnectionError')):
                        connection_dead = True
                    break
                msgs.append(msg)
                if not msg.get('tool_calls'):
                    if t < 2:
                        msgs.append({'role': 'user',
                                     'content': 'Call Edit or Write now — do not write prose.'})
                        continue
                    break
                for tc in msg['tool_calls']:
                    if _apply_repair_tool_call(tc, seen_states, consecutive_dups,
                                               msgs, syntax_check):
                        stuck = True
                edited = True
                break
            if connection_dead:
                print(f"==> [mu-agent] Repair: connection lost — aborting repair loop.")
                break
            if stuck:
                break
            if not edited:
                print(f"==> [mu-agent] Repair iter {i + 1}: model produced no edit.")

        if reapply:
            reapply()
        passed, _ = run_test()
        return passed, max_iters
