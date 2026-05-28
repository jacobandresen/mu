"""Reflect on recent failed sessions and distill generic lessons.

The `mu reflect` subcommand walks ~/.mu/sessions/, finds non-success
sessions that haven't yet been reflected on, and asks the configured
model to produce one generic challenge entry per session — or SKIP if
the failure isn't generalizable. Surviving entries are appended to the
project CHALLENGES.md under `## Open`, which the planner inlines on the
next run.

Honesty guards:
  * the prompt demands a *generic* failure mode and forbids
    problem-specific patches;
  * SKIP is a first-class outcome — if the model can't generalize, no
    entry is written;
  * sessions are deduplicated by id (state file in the archive root)
    so re-running is idempotent;
  * before appending, each candidate is checked against existing Open
    titles to avoid double-recording the same lesson.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from mu.client import chat_or_retry

_STATE_FILE = '.reflect-state.json'
_LOG_TAIL_BYTES = 4000
_REFLECT_TIMEOUT = 60.0


def _archive_dir() -> str:
    return (os.environ.get('MU_AGENT_ARCHIVE_DIR', '') or
            str(Path.home() / '.mu' / 'sessions'))


def _load_state() -> dict:
    path = Path(_archive_dir()) / _STATE_FILE
    if not path.exists():
        return {'reflected': []}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {'reflected': []}


def _save_state(state: dict) -> None:
    path = Path(_archive_dir()) / _STATE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2) + '\n', encoding='utf-8')
    except OSError:
        pass


def _recent_failures(limit: int) -> list[Path]:
    """Return up to `limit` most-recent non-success session directories."""
    root = Path(_archive_dir())
    if not root.is_dir():
        return []
    candidates = []
    for entry in sorted(root.iterdir(), reverse=True):
        if not entry.is_dir():
            continue
        meta_path = entry / 'meta.json'
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if meta.get('outcome') in (None, 'success', 'unknown'):
            continue
        candidates.append(entry)
        if len(candidates) >= limit:
            break
    return candidates


def _read_log_tail(session_dir: Path) -> str:
    logs = session_dir / 'logs'
    if not logs.is_dir():
        return ''
    log_files = sorted(logs.rglob('*'), key=lambda p: p.stat().st_mtime if p.is_file() else 0)
    log_files = [p for p in log_files if p.is_file()]
    if not log_files:
        return ''
    chosen = log_files[-1]
    try:
        data = chosen.read_bytes()
    except OSError:
        return ''
    if len(data) > _LOG_TAIL_BYTES:
        data = data[-_LOG_TAIL_BYTES:]
    try:
        return data.decode('utf-8', errors='replace')
    except Exception:
        return ''


def _existing_open_titles(challenges_path: str) -> list[str]:
    try:
        text = Path(challenges_path).read_text(encoding='utf-8')
    except OSError:
        return []
    if '## Open' not in text:
        return []
    section = text.split('## Open', 1)[1].split('## Resolved', 1)[0]
    return re.findall(r'^\d+\.\s+\*\*(.+?)\*\*', section, flags=re.MULTILINE)


def _is_duplicate(title: str, existing: list[str]) -> bool:
    norm = re.sub(r'\W+', ' ', title.lower()).strip()
    for ex in existing:
        ex_norm = re.sub(r'\W+', ' ', ex.lower()).strip()
        if norm and ex_norm and (norm in ex_norm or ex_norm in norm):
            return True
    return False


# Reject heuristics for "this is actually problem-specific" entries.
# Each is a clear, narrow signal — false positives here just lose a lesson,
# false negatives let problem-specific guidance pollute CHALLENGES.md.
_REJECT_YOUR = re.compile(r'\byour\b', re.IGNORECASE)
_REJECT_NAMED_TOOL = re.compile(
    r'\b(?:Flask|Django|FastAPI|Gin|SDL2?|pytest|dotnet|cargo|clang|gcc|'
    r'sqlite[0-9]?|tkinter|numpy|pandas|httpx|requests|Makefile)\b',
    re.IGNORECASE,
)
_REJECT_BACKTICKED_IDENTIFIER = re.compile(r'`[A-Za-z_][A-Za-z0-9_./-]*`')


def _is_problem_specific(entry: str) -> Optional[str]:
    """Return a short reason string if entry looks problem-specific, else None."""
    if _REJECT_YOUR.search(entry):
        return 'uses "your"'
    if _REJECT_NAMED_TOOL.search(entry):
        m = _REJECT_NAMED_TOOL.search(entry)
        return f'names tool/lib `{m.group(0)}`' if m else 'names tool/lib'
    if _REJECT_BACKTICKED_IDENTIFIER.search(entry):
        return 'cites a specific identifier in backticks'
    return None


def _ask_model(model: str, goal: str, outcome: str, log_tail: str,
               existing_titles: list[str]) -> str:
    """Return a single CHALLENGES entry, or 'SKIP' if no generic lesson."""
    system = (
        "You are reviewing one failed coding session from a dojo. Your job is "
        "to extract at most one *generic* recurring failure mode — something "
        "that would help future, unrelated tasks avoid the same trap.\n\n"
        "A lesson is GENERIC if it would apply to a session you have never seen, "
        "across different languages, libraries, and goals. A lesson is "
        "PROBLEM-SPECIFIC if it names a particular library, file, target, "
        "function, table, or framework feature from this session.\n\n"
        "Examples of acceptable GENERIC lessons:\n"
        "  - **Build target inconsistency** — Plans frequently name an entry-point\n"
        "    target the build file does not actually define; require the planner\n"
        "    to spell out every target the test command invokes.\n"
        "  - **Test state leaks across runs** — Tests sharing mutable storage\n"
        "    accumulate state between invocations; require setup/teardown that\n"
        "    isolates state per test.\n\n"
        "Examples that MUST be answered with SKIP because they are problem-specific:\n"
        "  - 'Add a run target to your Makefile that compiles the C# program.'\n"
        "  - 'Reset the todos table between pytest cases.'\n"
        "  - 'Install Flask before running the API.'\n\n"
        "STRICT RULES:\n"
        "- Reply SKIP if the failure is tied to a specific library, file name,\n"
        "  target, schema, or framework call.\n"
        "- Reply SKIP if the lesson duplicates one already on file.\n"
        "- Do NOT use the words 'your', 'this Makefile', 'the database', or any\n"
        "  other phrase that refers back to this session's artifacts.\n"
        "- Otherwise output ONE markdown list entry in this exact format:\n"
        "  **Short title (5-8 words)**\n"
        "    - One sentence describing the generic failure mode and what to watch for.\n"
        "- No preamble, no explanation, no code fences. Just SKIP or the entry."
    )
    existing_block = '\n'.join(f'- {t}' for t in existing_titles) or '(none)'
    user = (
        f"GOAL: {goal}\n"
        f"OUTCOME: {outcome}\n\n"
        f"Existing lessons on file (do not duplicate):\n{existing_block}\n\n"
        f"Tail of the session log:\n```\n{log_tail or '(no log captured)'}\n```\n\n"
        f"Distill at most one generic lesson, or SKIP."
    )
    msgs = [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': user},
    ]
    try:
        msg, _ = chat_or_retry(model, msgs, None,
                               time.time() + _REFLECT_TIMEOUT)
    except Exception as e:
        print(f"mu-reflect: chat error: {e}", file=sys.stderr)
        return 'SKIP'
    return (msg.get('content') or '').strip()


def _append_challenge(challenges_path: str, entry: str) -> bool:
    """Insert `entry` as the next numbered item in the ## Open section.

    Returns True if appended, False otherwise (parse failure, no Open section).
    """
    try:
        text = Path(challenges_path).read_text(encoding='utf-8')
    except OSError:
        return False
    if '## Open' not in text:
        return False
    pre, rest = text.split('## Open', 1)
    if '## Resolved' in rest:
        open_body, post = rest.split('## Resolved', 1)
        post = '## Resolved' + post
    else:
        open_body, post = rest, ''
    numbers = [int(n) for n in re.findall(r'^(\d+)\.\s+\*\*', open_body, flags=re.MULTILINE)]
    next_num = (max(numbers) + 1) if numbers else 1
    open_body = open_body.rstrip() + f'\n\n{next_num}. {entry.strip()}\n\n'
    new_text = pre + '## Open' + open_body + post
    try:
        Path(challenges_path).write_text(new_text, encoding='utf-8')
        return True
    except OSError:
        return False


def reflect(model: str = '', limit: int = 10,
            challenges_path: str = 'CHALLENGES.md') -> int:
    """Process up to `limit` recent failed sessions; append generic lessons."""
    if not model:
        model = os.environ.get('MU_AGENT_MODEL', '')
    if not model:
        try:
            from mu.agent import _select_model
            model = _select_model()
        except Exception:
            model = ''
    if not model:
        print("mu-reflect: no model available (set MU_AGENT_MODEL)", file=sys.stderr)
        return 1

    state = _load_state()
    seen = set(state.get('reflected') or [])
    candidates = _recent_failures(limit * 2)
    candidates = [c for c in candidates if c.name not in seen][:limit]
    if not candidates:
        print("mu-reflect: no new failed sessions to reflect on.")
        return 0

    appended = 0
    skipped = 0
    for session_dir in candidates:
        try:
            meta = json.loads((session_dir / 'meta.json').read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        goal = meta.get('goal', '')
        outcome = meta.get('outcome', 'unknown')
        log_tail = _read_log_tail(session_dir)
        existing = _existing_open_titles(challenges_path)
        result = _ask_model(model, goal, outcome, log_tail, existing)

        if not result or result.strip().upper() == 'SKIP':
            skipped += 1
            seen.add(session_dir.name)
            continue

        title_match = re.search(r'\*\*(.+?)\*\*', result)
        title = title_match.group(1) if title_match else ''
        if not title:
            skipped += 1
            seen.add(session_dir.name)
            continue
        if _is_duplicate(title, existing):
            skipped += 1
            seen.add(session_dir.name)
            continue
        reason = _is_problem_specific(result)
        if reason:
            skipped += 1
            print(f"  - {session_dir.name}: rejected ({reason})")
            seen.add(session_dir.name)
            continue

        if _append_challenge(challenges_path, result):
            appended += 1
            print(f"  + {session_dir.name}: appended «{title or '(untitled)'}»")
        else:
            skipped += 1
        seen.add(session_dir.name)

    state['reflected'] = sorted(seen)
    _save_state(state)
    print(f"mu-reflect: appended {appended}, skipped {skipped}, "
          f"processed {len(candidates)} session(s).")
    return 0
