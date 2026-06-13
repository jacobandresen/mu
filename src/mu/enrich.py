"""Learning element (retrieval/recall): ASKs the knowledge base for relevant lessons.

In AIMA terms this is the **learning element's retrieval arm** — it reads the
episodic memory (``~/.mu/sessions/``) and the mutable knowledge base
(``docs/challenges/lessons.md``) and surfaces lessons that are semantically relevant to the
current goal. This is an ASK operation on the knowledge base, in contrast to
``reflect`` which TELLs it.

The retriever uses sentence-transformers to embed docs/challenges/lessons.md entries plus a
per-session goal index, and returns lessons whose semantic neighbourhood in the
archive contains enough prior failures to corroborate them.

The sentence_transformers and numpy imports are lazy. If either is missing,
every public function no-ops and returns empty results.

Two honesty guards keep retrieval generic, not problem-specific:
  * corroboration: at least _CORROBORATION_MIN prior archived sessions near the
    goal must have a non-success outcome before any lesson is surfaced;
  * concentration cap: no lesson is returned if it has been injected into more
    than _CONCENTRATION_CAP of recent plan generations.
"""

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Optional

_MODEL_NAME = 'all-MiniLM-L6-v2'
_INDEX_FILE = '.enrich-index.jsonl'
_LESSON_LOG = '.enrich-lessons.jsonl'
_LOG_WINDOW = 50
_LOG_WARMUP = 10
_CONCENTRATION_CAP = 0.4
_CORROBORATION_MIN = 3
_SIMILARITY_THRESHOLD = 0.45


def _archive_dir() -> str:
    return (os.environ.get('MU_AGENT_ARCHIVE_DIR', '') or
            str(Path.home() / '.mu' / 'sessions'))


def _model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    cached = getattr(_model, '_cached', None)
    if cached is None:
        try:
            cached = SentenceTransformer(_MODEL_NAME)
        except Exception:
            return None
        _model._cached = cached  # type: ignore[attr-defined]
    return cached


def _embed(texts: list[str]):
    m = _model()
    if m is None or not texts:
        return None
    try:
        import numpy as np
    except ImportError:
        return None
    try:
        return np.asarray(m.encode(texts, normalize_embeddings=True))
    except Exception:
        return None


def open_challenges(challenges_path: str = 'docs/challenges/lessons.md') -> list[str]:
    """Parse the Open section of docs/challenges/lessons.md into one string per entry."""
    try:
        text = Path(challenges_path).read_text(encoding='utf-8')
    except OSError:
        return []
    if '## Open' not in text:
        return []
    section = text.split('## Open', 1)[1].split('## Resolved', 1)[0]
    entries = re.findall(
        r'^\d+\.\s+\*\*(.+?)\*\*\s*\n((?:\s+-.*\n?)+)',
        section, flags=re.MULTILINE,
    )
    out: list[str] = []
    for title, body in entries:
        body_clean = re.sub(r'\s+', ' ', body).strip()
        out.append(f'{title}: {body_clean}')
    return out


def index_session(session_path: str) -> None:
    """Append an index entry for one finalized session. Failures are silent.

    Called from Archive.finalize. Embedding is computed eagerly so query
    time stays cheap; if embeddings aren't available the entry is still
    written so it can be backfilled later.
    """
    try:
        meta = json.loads((Path(session_path) / 'meta.json').read_text())
    except (OSError, json.JSONDecodeError):
        return
    goal = meta.get('goal') or ''
    if not goal:
        return
    emb = _embed([goal])
    entry = {
        'id': meta.get('session_id', ''),
        'goal': goal,
        'outcome': meta.get('outcome', 'unknown'),
        'embedding': emb[0].tolist() if emb is not None else None,
    }
    idx_path = Path(_archive_dir()) / _INDEX_FILE
    try:
        idx_path.parent.mkdir(parents=True, exist_ok=True)
        with idx_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')
    except OSError:
        pass


def _load_index() -> list[dict]:
    idx_path = Path(_archive_dir()) / _INDEX_FILE
    if not idx_path.exists():
        return []
    out: list[dict] = []
    try:
        for line in idx_path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def _concentration(candidate_id: str) -> Optional[float]:
    log_path = Path(_archive_dir()) / _LESSON_LOG
    if not log_path.exists():
        return None
    try:
        lines = log_path.read_text(encoding='utf-8').splitlines()[-_LOG_WINDOW:]
    except OSError:
        return None
    counts: Counter[str] = Counter()
    n = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            ids = json.loads(line).get('lessons') or []
        except json.JSONDecodeError:
            continue
        n += 1
        for lid in ids:
            counts[lid] += 1
    if n < _LOG_WARMUP:
        return None
    return counts[candidate_id] / n


def _bump_log(lesson_ids: list[str]) -> None:
    if not lesson_ids:
        return
    log_path = Path(_archive_dir()) / _LESSON_LOG
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'lessons': lesson_ids}) + '\n')
    except OSError:
        pass


def lessons_for(goal: str, k: int = 3,
                challenges_path: str = 'docs/challenges/lessons.md') -> list[str]:
    """Return up to k lessons semantically relevant to the goal.

    Returns [] when embeddings are unavailable, when no challenges exist,
    when fewer than _CORROBORATION_MIN nearby prior failures back the
    semantic neighbourhood, or when no challenge clears the similarity
    threshold. Concentration-blocked lessons are skipped but the next
    candidate is still considered.
    """
    if not goal:
        return []
    challenges = open_challenges(challenges_path)
    if not challenges:
        return []
    goal_emb_arr = _embed([goal])
    if goal_emb_arr is None:
        return []
    import numpy as np
    goal_emb = goal_emb_arr[0]

    nearby_failures = 0
    for entry in _load_index():
        emb = entry.get('embedding')
        if not emb:
            continue
        sim = float(np.dot(goal_emb, np.asarray(emb)))
        outcome = entry.get('outcome', 'unknown')
        if sim >= _SIMILARITY_THRESHOLD and outcome not in ('success', 'unknown'):
            nearby_failures += 1
    if nearby_failures < _CORROBORATION_MIN:
        return []

    chal_emb = _embed(challenges)
    if chal_emb is None:
        return []
    sims = chal_emb @ goal_emb
    order = np.argsort(-sims)
    out: list[str] = []
    chosen_ids: list[str] = []
    for i in order:
        if float(sims[i]) < _SIMILARITY_THRESHOLD:
            break
        lesson = challenges[int(i)]
        lid = lesson.split(':', 1)[0]
        conc = _concentration(lid)
        if conc is not None and conc > _CONCENTRATION_CAP:
            continue
        out.append(lesson)
        chosen_ids.append(lid)
        if len(out) >= k:
            break
    _bump_log(chosen_ids)
    return out


def render_lessons_section(lessons: list[str]) -> str:
    """Format lessons as a `## Lessons From Prior Runs` section."""
    if not lessons:
        return ''
    body = '\n'.join(f'- {ln}' for ln in lessons)
    return f'## Lessons From Prior Runs\n\n{body}\n'
