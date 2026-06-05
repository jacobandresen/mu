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
        self.start_time = datetime.now(timezone.utc)
        self.archive_path = os.path.join(archive_dir, self.id)
        self.max_iter = max_iter
        self.log_dir = log_dir
        self.repair_iters = 0  # accumulated by caller across all test-gate repair loops
        os.makedirs(self.archive_path, exist_ok=True)
        try:
            Path(os.path.join(self.archive_path, 'meta.json')).write_text(
                json.dumps({'session_id': self.id, 'goal': goal,
                            'outcome': 'unknown', 'exit_code': -1}) + '\n')
        except OSError:
            pass

    def finalize(self, exit_code: int, p: Optional[Plan],
                 plan_file: str = 'PLAN.md') -> None:
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
        meta = {
            'session_id': self.id, 'goal': self.goal,
            'model': self.model,
            'project_dir': self.project_dir,
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': wall_seconds,
            'max_iterations': self.max_iter,
            'exit_code': exit_code,
            **utility.as_dict(),
        }
        try:
            Path(os.path.join(self.archive_path, 'meta.json')).write_text(
                json.dumps(meta, indent=2) + '\n')
            print(f"==> [mu-agent] Session archived -> {self.archive_path}",
                  flush=True)
        except OSError:
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
