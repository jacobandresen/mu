"""Episodic memory: session tombstones in ~/.mu/sessions/.

In AIMA terms this module is the agent's **episodic memory** — the experience
store that the learning element (``reflect``, ``enrich``) reads to distill
lessons and retrieve relevant past failures. Each session directory is one
episode; ``meta.json`` is the episode's summary including the ``Utility``
record emitted by the critic.
"""

import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mu.plan import Plan, count_tasks


@dataclass
class Utility:
    """Performance measure emitted by the critic at the end of each episode.

    Fields match the PEAS performance measure defined in the AIMA architecture
    doc. ``first_try_pass`` and ``repair_iters`` capture the quality of the
    performance element's execution; the learner reads these to weight lessons.
    """
    outcome: str          # success / error / max_iterations / stalled / interrupted
    first_try_pass: bool  # tests passed with zero repair iterations
    repair_iters: int     # total repair loop iterations across all test gates
    wall_seconds: int     # total run duration
    tasks_total: int      # tasks in PLAN.md
    tasks_done: int       # tasks marked done

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def load(cls, session_dir: str) -> Optional['Utility']:
        """Load from a finalized session directory's meta.json."""
        try:
            meta = json.loads((Path(session_dir) / 'meta.json').read_text())
            return cls(
                outcome=meta.get('outcome', 'unknown'),
                first_try_pass=meta.get('first_try_pass', False),
                repair_iters=meta.get('repair_iters', 0),
                wall_seconds=meta.get('duration_seconds', 0),
                tasks_total=meta.get('tasks_total', 0),
                tasks_done=meta.get('tasks_done', 0),
            )
        except (OSError, json.JSONDecodeError, KeyError):
            return None


class AgentSession:
    def __init__(self, goal: str, archive_dir: str, log_dir: str, max_iter: int,
                 model: str = ''):
        safe = re.sub(r'[^A-Za-z0-9_-]', '',
                      goal.replace(' ', '_').replace('/', '-'))[:40]
        self.id = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + safe
        self.goal = goal
        # The model that produced this episode. Persisted so observations
        # (failures, reflex firings) can be attributed to the model that made
        # them — granite and qwen fail differently, so a lesson valid for one
        # may not hold for the other (see docs/REFLEX_KB.md model stratification).
        self.model = model
        self.project_dir = os.getcwd()
        try:  # start a clean firing log for this episode (reflex KB)
            from mu.reflexes.core import reset_firings
            reset_firings()
        except Exception:
            pass
        try:  # start a clean degeneration-guard refusal count for this episode
            from mu.degeneration import reset_refusals
            reset_refusals()
        except Exception:
            pass
        self.start_time = datetime.now(timezone.utc)
        self.archive_path = os.path.join(archive_dir, self.id)
        self.max_iter = max_iter
        self.log_dir = log_dir
        # Truncate the teed agent event log so the archive holds only this
        # session's events — work dirs are reused across runs outside the dojo.
        try:
            os.makedirs(log_dir, exist_ok=True)
            open(os.path.join(log_dir, 'agent.log'), 'w').close()
        except OSError:
            pass
        self.repair_iters = 0  # accumulated by caller across all test-gate repair loops
        # One-line machine-readable cause, set by the caller at the failure
        # exit point (e.g. "tests failing after repair for app.py"). Persisted
        # in meta.json so failure scans don't have to parse logs for the cause.
        self.fail_reason = ''
        self._finalized = False
        os.makedirs(self.archive_path, exist_ok=True)
        try:
            Path(os.path.join(self.archive_path, 'meta.json')).write_text(
                json.dumps({'session_id': self.id, 'goal': goal,
                            'outcome': 'unknown', 'exit_code': -1,
                            'project_dir': self.project_dir}) + '\n')
        except OSError:
            pass

    def finalize(self, exit_code: int, p: Optional[Plan],
                 plan_file: str = 'PLAN.md') -> None:
        # Idempotent: the signal handler finalizes with 130 and then unwinds
        # through run()'s finally, which would finalize again with the stale
        # local exit_code (often 0) and overwrite the interrupted session's
        # meta as 'success'. First write wins.
        if self._finalized:
            return
        self._finalized = True
        os.makedirs(os.path.join(self.archive_path, 'logs'), exist_ok=True)
        if os.path.isdir(self.log_dir):
            _copy_dir(self.log_dir, os.path.join(self.archive_path, 'logs'))
        tasks_total, tasks_done = (0, 0) if p is None else count_tasks(p)
        if p is not None:
            try:
                shutil.copy2(plan_file, os.path.join(self.archive_path, 'PLAN-final.md'))
            except OSError:
                pass
        outcome_map = {0: 'success', 1: 'error', 2: 'max_iterations',
                       3: 'stalled', 4: 'predicted_abort', 130: 'interrupted'}
        end_time = datetime.now(timezone.utc)
        wall_seconds = int((end_time - self.start_time).total_seconds())
        outcome = outcome_map.get(exit_code, 'unknown')

        utility = Utility(
            outcome=outcome,
            first_try_pass=self.repair_iters == 0 and outcome == 'success',
            repair_iters=self.repair_iters,
            wall_seconds=wall_seconds,
            tasks_total=tasks_total,
            tasks_done=tasks_done,
        )
        try:  # how often the degeneration guard refused a corrupt write this episode
            from mu.degeneration import refusal_count
            degen_refusals = refusal_count()
        except Exception:
            degen_refusals = 0
        if degen_refusals:
            print(f"==> [mu-agent] Degeneration guard refused {degen_refusals} "
                  f"write(s) this session.", flush=True)
        meta = {
            'session_id': self.id, 'goal': self.goal,
            'model': self.model,
            'fail_reason': self.fail_reason,
            'project_dir': self.project_dir,
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': wall_seconds,
            'max_iterations': self.max_iter,
            'exit_code': exit_code,
            'degeneration_refusals': degen_refusals,
            **utility.as_dict(),
        }
        try:
            Path(os.path.join(self.archive_path, 'meta.json')).write_text(
                json.dumps(meta, indent=2) + '\n')
            print(f"==> [mu-agent] Session archived -> {self.archive_path}",
                  flush=True)
        except OSError:
            pass
        try:  # flush this episode's reflex firings for the reflex KB
            from mu.reflexes.core import get_firings
            firings = get_firings()
            if firings:
                (Path(self.archive_path) / 'firings.jsonl').write_text(
                    '\n'.join(json.dumps(e) for e in firings) + '\n', encoding='utf-8')
        except Exception:
            pass
        try:
            from mu.enrich import index_session
            index_session(self.archive_path)
        except ImportError:
            pass  # enrich optional dependency not installed
        except Exception as e:
            print(f"==> [mu-agent] Warning: enrichment indexing failed: {e}", flush=True)
        try:
            from mu.client import flush_token_log
            token_entries = flush_token_log()
            if token_entries:
                tokens_path = Path(self.archive_path) / 'tokens.jsonl'
                tokens_path.write_text(
                    '\n'.join(json.dumps(e) for e in token_entries) + '\n',
                    encoding='utf-8',
                )
                # Append per-phase summary to meta.json
                phase_totals: dict[str, dict[str, int]] = {}
                for e in token_entries:
                    ph = e.get('phase') or 'unknown'
                    bucket = phase_totals.setdefault(ph, {'prompt': 0, 'generated': 0})
                    bucket['prompt'] += e.get('prompt_tokens', 0)
                    bucket['generated'] += e.get('generated_tokens', 0)
                total_prompt = sum(b['prompt'] for b in phase_totals.values())
                total_generated = sum(b['generated'] for b in phase_totals.values())
                meta['total_prompt_tokens'] = total_prompt
                meta['total_generated_tokens'] = total_generated
                meta['tokens_by_phase'] = phase_totals
                Path(os.path.join(self.archive_path, 'meta.json')).write_text(
                    json.dumps(meta, indent=2) + '\n')
                (Path(self.archive_path) / 'token_usage.md').write_text(
                    _render_token_usage_md(meta), encoding='utf-8')
        except Exception as e:
            print(f"==> [mu-agent] Warning: token log save failed: {e}", flush=True)
        # Failures get the full forensic record: what the model was asked and
        # replied (transcript) and what it actually left on disk (workspace).
        # Successes don't need it, and the per-session cost would add up.
        if outcome != 'success':
            try:
                from mu.client import flush_transcript
                entries = flush_transcript()
                if entries:
                    (Path(self.archive_path) / 'transcript.jsonl').write_text(
                        '\n'.join(json.dumps(e) for e in entries) + '\n',
                        encoding='utf-8')
            except Exception as e:
                print(f"==> [mu-agent] Warning: transcript save failed: {e}", flush=True)
            try:
                _snapshot_workspace(self.project_dir,
                                    os.path.join(self.archive_path, 'workspace'))
            except Exception as e:
                print(f"==> [mu-agent] Warning: workspace snapshot failed: {e}", flush=True)
        else:
            try:  # clear the buffer so the next session starts clean
                from mu.client import flush_transcript
                flush_transcript()
            except Exception:
                pass


# Workspace snapshot limits: enough for any realistic dojo problem source
# tree, small enough that a runaway artifact dir can't bloat the archive.
_SNAP_FILE_CAP = 65536       # bytes kept per file (head)
_SNAP_TOTAL_CAP = 2_000_000  # bytes across the whole snapshot
_SNAP_SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv',
                   'target', 'bin', 'obj', 'dist', 'build', '.mu',
                   'coverage', '.pytest_cache'}


def _snapshot_workspace(project_dir: str, dst: str) -> None:
    """Copy the (capped) source tree of a failed session into the archive.

    A failed archive without the workspace can show *that* a test failed but
    not the code that failed it. TREE.txt lists everything seen, including
    files skipped by the caps, so the listing is complete even when the
    contents aren't.
    """
    tree_lines: list[str] = []
    used = 0
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = sorted(d for d in dirs if d not in _SNAP_SKIP_DIRS)
        for name in sorted(files):
            sp = os.path.join(root, name)
            rel = os.path.relpath(sp, project_dir)
            try:
                size = os.path.getsize(sp)
            except OSError:
                continue
            note = ''
            try:
                with open(sp, 'rb') as fh:
                    head = fh.read(_SNAP_FILE_CAP)
                if b'\x00' in head[:1024]:
                    note = 'binary, skipped'
                elif used + len(head) > _SNAP_TOTAL_CAP:
                    note = 'total cap reached, skipped'
                else:
                    dp = os.path.join(dst, rel)
                    os.makedirs(os.path.dirname(dp), exist_ok=True)
                    with open(dp, 'wb') as out:
                        out.write(head)
                    used += len(head)
                    if size > _SNAP_FILE_CAP:
                        note = f'truncated to {_SNAP_FILE_CAP}'
            except OSError:
                note = 'unreadable, skipped'
            tree_lines.append(f'{size:>9}  {rel}' + (f'  [{note}]' if note else ''))
    if tree_lines:
        os.makedirs(dst, exist_ok=True)
        Path(os.path.join(dst, 'TREE.txt')).write_text(
            '\n'.join(tree_lines) + '\n', encoding='utf-8')


def _render_token_usage_md(meta: dict) -> str:
    """Render a per-session token_usage.md from a finalized meta dict."""
    goal = meta.get('goal', 'unknown')
    outcome = meta.get('outcome', 'unknown')
    wall = meta.get('duration_seconds', 0)
    repair_iters = meta.get('repair_iters', 0)
    total_p = meta.get('total_prompt_tokens', 0)
    total_g = meta.get('total_generated_tokens', 0)
    phase_totals: dict = meta.get('tokens_by_phase', {})

    rows = sorted(phase_totals.items(),
                  key=lambda kv: kv[1]['prompt'] + kv[1]['generated'],
                  reverse=True)

    lines = [
        '# Token Usage',
        '',
        f'**Goal:** {goal}  ',
        f'**Outcome:** {outcome}  ',
        f'**Wall time:** {wall}s  ',
        f'**Repair iterations:** {repair_iters}  ',
        '',
        '## Totals',
        '',
        '| Metric | Tokens |',
        '|---|---|',
        f'| Prompt | {total_p:,} |',
        f'| Generated | {total_g:,} |',
        f'| Total | {total_p + total_g:,} |',
        '',
        '## By Phase',
        '',
        '| Phase | Prompt | Generated |',
        '|---|---|---|',
    ]
    for phase, bucket in rows:
        lines.append(f'| {phase} | {bucket["prompt"]:,} | {bucket["generated"]:,} |')
    lines.append('')
    return '\n'.join(lines)


def _copy_dir(src: str, dst: str) -> None:
    os.makedirs(dst, exist_ok=True)
    try:
        for e in os.scandir(src):
            sp, dp = os.path.join(src, e.name), os.path.join(dst, e.name)
            _copy_dir(sp, dp) if e.is_dir() else shutil.copy2(sp, dp)
    except OSError:
        pass
