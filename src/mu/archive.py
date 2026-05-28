"""Session archiving: tombstones in ~/.mu/sessions/."""

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mu.plan import Plan, count_tasks


class AgentSession:
    def __init__(self, goal: str, archive_dir: str, log_dir: str, max_iter: int):
        safe = re.sub(r'[^A-Za-z0-9_-]', '',
                      goal.replace(' ', '_').replace('/', '-'))[:40]
        self.id = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + safe
        self.goal = goal
        self.project_dir = os.getcwd()
        self.start_time = datetime.now(timezone.utc)
        self.archive_path = os.path.join(archive_dir, self.id)
        self.max_iter = max_iter
        self.log_dir = log_dir
        os.makedirs(self.archive_path, exist_ok=True)
        try:
            Path(os.path.join(self.archive_path, 'meta.json')).write_text(
                json.dumps({'session_id': self.id, 'goal': goal,
                            'outcome': 'unknown', 'exit_code': -1}) + '\n')
        except OSError:
            pass

    def finalize(self, exit_code: int, p: Optional[Plan]) -> None:
        os.makedirs(os.path.join(self.archive_path, 'logs'), exist_ok=True)
        if os.path.isdir(self.log_dir):
            _copy_dir(self.log_dir, os.path.join(self.archive_path, 'logs'))
        tasks_total, tasks_done = (0, 0) if p is None else count_tasks(p)
        if p is not None:
            try:
                shutil.copy2('PLAN.md', os.path.join(self.archive_path, 'PLAN-final.md'))
            except OSError:
                pass
        outcome_map = {0: 'success', 1: 'error', 2: 'max_iterations',
                       3: 'stalled', 130: 'interrupted'}
        end_time = datetime.now(timezone.utc)
        meta = {
            'session_id': self.id, 'goal': self.goal,
            'project_dir': self.project_dir,
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': int((end_time - self.start_time).total_seconds()),
            'max_iterations': self.max_iter,
            'outcome': outcome_map.get(exit_code, 'unknown'),
            'exit_code': exit_code,
            'tasks_total': tasks_total, 'tasks_done': tasks_done,
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
        except Exception:
            pass


def _copy_dir(src: str, dst: str) -> None:
    os.makedirs(dst, exist_ok=True)
    try:
        for e in os.scandir(src):
            sp, dp = os.path.join(src, e.name), os.path.join(dst, e.name)
            _copy_dir(sp, dp) if e.is_dir() else shutil.copy2(sp, dp)
    except OSError:
        pass
