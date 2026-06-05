"""Read finalized sessions out of the archive.

The scripts found sessions with ``find … -name meta.json -newer "$marker"`` and
scraped fields with ``awk -F'"'``. Here a session is a :class:`SessionMeta`
dataclass loaded with :func:`json.load`, and the marker is just a timestamp —
no temp file, no quoting games. Both ``measure`` and ``practice`` consume this.
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .env import archive_dir


@dataclass(frozen=True)
class SessionMeta:
    """One finalized session, as recorded in its ``meta.json``."""

    path: Path           # the meta.json itself
    outcome: str         # 'success' | 'stalled' | 'error' | 'unknown'
    goal: str
    session_id: str
    project_dir: str
    model: str
    repair_iters: int

    @property
    def dir(self) -> Path:
        """The session directory (parent of meta.json)."""
        return self.path.parent

    @property
    def problem_id(self) -> str:
        """Problem id (p7-flask, …) from the project dir basename — more reliable
        than goal-text matching for the per-problem summary."""
        return Path(self.project_dir).name or 'unknown'

    @property
    def passed(self) -> bool:
        return self.outcome == 'success'


def _load(meta_path: Path) -> Optional[SessionMeta]:
    try:
        d = json.loads(meta_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return SessionMeta(
        path=meta_path,
        outcome=d.get('outcome') or 'unknown',
        goal=d.get('goal') or '?',
        session_id=d.get('session_id') or '?',
        project_dir=d.get('project_dir') or 'unknown',
        model=d.get('model') or '?',
        repair_iters=int(d.get('repair_iters') or 0),
    )


def now() -> float:
    """A marker timestamp. Capture before a round, pass to :func:`sessions_since`
    afterward to pick up exactly the sessions finalized in between."""
    return time.time()


def sessions_since(marker: float, archive: Optional[Path] = None) -> list[SessionMeta]:
    """Sessions whose ``meta.json`` was written after *marker*, oldest first.

    Uses mtime (not creation) so a session whose meta.json is *rewritten* during
    finalize() is picked up — the reason the scripts used ``find -newer``."""
    root = archive or archive_dir()
    found: list[tuple[float, SessionMeta]] = []
    for meta in root.glob('*/meta.json'):
        try:
            mtime = meta.stat().st_mtime
        except OSError:
            continue
        if mtime <= marker:
            continue
        sm = _load(meta)
        if sm is not None:
            found.append((mtime, sm))
    return [sm for _, sm in sorted(found, key=lambda t: t[0])]


def latest_since(marker: float, archive: Optional[Path] = None) -> Optional[SessionMeta]:
    """The single most-recently-finalized session after *marker* (what ``measure``
    wants: the one run it just kicked off)."""
    found = sessions_since(marker, archive)
    return found[-1] if found else None


def root_cause(session_dir: Path) -> str:
    """Distill the one-line general-class cause from a session's archived logs,
    using mu's own diagnose sensor — the same hint that leads the repair prompt.

    Turns a digest line from "stalled: <goal>" into
    "stalled: <goal> -- cause: NameError 'app' not defined", so a human (or the
    next round's reflect step) sees the exact error class without reopening logs.
    Returns '' when nothing actionable is found."""
    logs = session_dir / 'logs'
    candidates = sorted(logs.glob('tests*.log'), key=lambda p: p.stat().st_mtime, reverse=True) \
        or sorted(logs.glob('lint*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return ''
    try:
        from mu.diagnose import distill_test_errors
        text = candidates[0].read_text(encoding='utf-8', errors='replace')
        hint = distill_test_errors(text)
    except Exception:
        return ''
    return _first_cause(hint)


def _first_cause(hint: str) -> str:
    """Pull the bare cause out of a diagnose hint, dropping the ``FOCUS …:``
    prefix (single-hint form) or taking the first bullet (multi-hint form)."""
    import re
    if not hint:
        return ''
    first = hint.splitlines()[0]
    m = re.match(r'FOCUS[^:]*:\s*(.+)', first)
    if m:
        return m.group(1).strip()
    for line in hint.splitlines()[1:]:
        line = line.strip().lstrip('-').strip()
        if line:
            return line
    return ''
