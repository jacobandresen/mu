"""Core reflex infrastructure: the fixpoint runner that chains reflexes to a
stable state, plus a few generic, language-agnostic fixers (tool-call artifact
stripping, literal-newline repair, JSON bracket balancing). The per-language
modules import :func:`run_reflexes` from here. No logic changes from the
original.
"""

import hashlib
import json
import os
from pathlib import Path


__all__ = [
    'run_reflexes',
    'fix_tool_call_artifacts',
    'fix_json_unclosed_brackets',
    'fix_literal_newlines',
]


def _file_sha(path: str) -> str:
    try:
        return hashlib.sha1(Path(path).read_bytes()).hexdigest()
    except OSError:
        return ''


# ── firing recorder (for the reflex KB) ───────────────────────────────────────
# run_reflexes notes which reflex actually changed a file, so the session can be
# attributed: which mistakes the model made, by model. The agent resets this at
# session start and flushes it to firings.jsonl at archive time.
_FIRINGS: list[dict] = []


def reset_firings() -> None:
    _FIRINGS.clear()


def get_firings() -> list[dict]:
    return list(_FIRINGS)


def note_fired(reflex_id: str, file: str = '', pass_index: int = 0) -> None:
    """Record that a reflex changed a file. Cheap no-op when unused."""
    _FIRINGS.append({'reflex_id': reflex_id, 'file': file, 'pass_index': pass_index})


def disabled_reflexes() -> set[str]:
    """Reflex names switched off via ``MU_DISABLE_REFLEX`` (comma-separated) — the
    ablation hook (docs/REFLEX_KB.md §9). Read per call so a subprocess set by
    ``mu dojo measure --disable`` takes effect, and tests can toggle it. Empty by
    default, so normal runs are unaffected."""
    return {n.strip() for n in os.environ.get('MU_DISABLE_REFLEX', '').split(',') if n.strip()}

def run_reflexes(fns, target: str, max_passes: int = 4) -> None:
    """Apply a chain of single-arg reflexes to a fixpoint — safely.

    Runs every reflex in order, repeating the whole chain until the file stops
    changing. This lets a reflex that only becomes applicable after an earlier
    one's edit (e.g. hoist a nested target, THEN add its missing rule) still fire,
    without hand-tuning a single pass order. It guards against the two ways a
    reflex chain can misbehave:

      * looping       — a hard ``max_passes`` cap.
      * contradicting — if the content returns to a state seen on an earlier pass
        (two reflexes undoing each other), stop immediately and log it rather
        than oscillate forever.

    A reflex that raises is skipped, never crashing the chain. Reflexes should be
    idempotent; the guards make a non-idempotent or contradictory pair *safe*
    (it stops, logged) instead of hanging.
    """
    disabled = disabled_reflexes()
    if disabled:
        fns = [fn for fn in fns if getattr(fn, '__name__', '') not in disabled]
    last = _file_sha(target)
    seen = {last}
    for pass_index in range(max_passes):
        before = last
        for fn in fns:
            try:
                fn(target)
            except Exception:
                pass
            after = _file_sha(target)
            if after != before:  # this reflex changed the file — record the firing
                note_fired(getattr(fn, '__name__', str(fn)), target, pass_index)
                before = after
        h = _file_sha(target)
        if h == last:
            return  # converged — a full pass changed nothing
        if h in seen:
            print(f"==> [mu-agent] Reflex contradiction on {target} — two reflexes "
                  f"oscillating; stopping at a stable-enough state.", flush=True)
            return
        seen.add(h)
        last = h
    print(f"==> [mu-agent] Reflexes did not converge on {target} after "
          f"{max_passes} passes — continuing with current state.", flush=True)

_CODE_EXTS = {'.py', '.cs', '.rs', '.go', '.c', '.cpp', '.h', '.java', '.js', '.ts', '.jsx', '.tsx', '.vue'}

def fix_tool_call_artifacts(file_path: str) -> bool:
    """Strip lines containing model tool-call JSON leaked into source files.

    Models occasionally embed their own tool-calling syntax (e.g. lines starting
    with backtick sequences followed by [TOOL_REQUEST]) directly into file content,
    producing immediate syntax errors. Generic: any such line in any source file
    is wrong.
    """
    p = Path(file_path)
    if p.suffix.lower() not in _CODE_EXTS and p.name.lower() not in ('makefile', 'requirements.txt'):
        return False
    try:
        text = p.read_text()
    except OSError:
        return False
    lines = text.splitlines(keepends=True)
    cleaned = [ln for ln in lines if '[TOOL_REQUEST]' not in ln and '[TOOL_RESULT]' not in ln]
    if len(cleaned) == len(lines):
        return False
    Path(file_path).write_text(''.join(cleaned))
    print(f"==> [mu-agent] Reflex: stripped tool-call artifact line(s) from {file_path}")
    return True

def fix_json_unclosed_brackets(file_path: str) -> bool:
    """Close unclosed JSON arrays or objects by appending missing brackets.

    Models sometimes truncate JSON files (tsconfig.json, package.json, etc.)
    mid-array or mid-object, causing 'Expected "," in JSON but found end of file'
    or 'Unterminated string' errors. This reflex counts open brackets and appends
    the missing closing ones in reverse order.
    General: applies to any .json file with unbalanced brackets.
    """
    if not file_path.lower().endswith('.json'):
        return False
    try:
        text = Path(file_path).read_text()
        json.loads(text)
        return False  # already valid
    except (json.JSONDecodeError, OSError):
        pass
    # Count brackets outside strings
    stack = []
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"':
            i += 1
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
        elif c == '[':
            stack.append(']')
        elif c == '{':
            stack.append('}')
        elif c == ']':
            if stack and stack[-1] == ']':
                stack.pop()
        elif c == '}':
            if stack and stack[-1] == '}':
                stack.pop()
        i += 1
    if not stack:
        return False  # brackets balanced — issue is something else
    # Append missing closing brackets in reverse order
    suffix = '\n' + ''.join(reversed(stack))
    new_text = text.rstrip() + suffix + '\n'
    try:
        json.loads(new_text)
    except json.JSONDecodeError:
        return False  # couldn't fix it
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: closed {len(stack)} unclosed bracket(s) in {file_path}")
    return True

def _fix_duplicate_decls(
    file_path: str,
    match_fn,
    keepends: bool = True,
) -> int:
    """Keep-first dedup of declaration lines; return count removed (0 = no change).

    match_fn(raw_line) -> key string (dedup by) or None (leave line as-is).
    keepends=True preserves original line endings (Rust path); False normalises
    to LF via splitlines()+join (JS path).
    """
    try:
        text = Path(file_path).read_text()
    except OSError:
        return 0
    lines = text.splitlines(keepends=keepends)
    seen: set[str] = set()
    result = []
    removed = 0
    for line in lines:
        key = match_fn(line)
        if key is not None:
            if key in seen:
                removed += 1
                continue
            seen.add(key)
        result.append(line)
    if not removed:
        return 0
    if keepends:
        Path(file_path).write_text(''.join(result))
    else:
        Path(file_path).write_text('\n'.join(result) + '\n')
    return removed


def fix_literal_newlines(file_path: str, lint_error: str = '') -> bool:
    """Replace literal \\n escape sequences with real newlines in source files.

    Models occasionally write an entire file as one long string with \\n
    characters instead of actual line breaks.

    Two modes:
    - Bulk mode: fires when literal \\n sequences outnumber real newlines by a
      wide margin (whole-file collapse). Safe to do a global replace on any
      source file.
    - Targeted mode (lint_error contains 'line continuation'): fires even in
      mixed files, but only replaces literal \\n outside string literals.
    """
    allowed_exts = _CODE_EXTS | {'.json'}
    if Path(file_path).suffix.lower() not in allowed_exts:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    real_newlines = text.count('\n')
    literal_newlines = text.count('\\n')
    if literal_newlines == 0:
        return False

    # JSON mode: ANY literal \n outside a JSON string value is invalid — fire on even 1.
    if Path(file_path).suffix.lower() == '.json' and literal_newlines >= 1:
        fixed = text.replace('\\n', '\n')
        Path(file_path).write_text(fixed)
        print(f"==> [mu-agent] Reflex: replaced {literal_newlines} literal \\n "
              f"with real newlines in {file_path}")
        return True

    # Bulk mode: nearly all newlines are literal (whole-file collapse).
    if literal_newlines >= 3 and literal_newlines > real_newlines:
        fixed = text.replace('\\n', '\n')
        Path(file_path).write_text(fixed)
        print(f"==> [mu-agent] Reflex: replaced {literal_newlines} literal \\n "
              f"with real newlines in {file_path}")
        return True

    # JS/TS mode: even one literal \n outside a string is a syntax error.
    # JavaScript has no line-continuation character, so any \n in code is wrong.
    ext = Path(file_path).suffix.lower()
    is_js = ext in ('.js', '.jsx', '.ts', '.tsx')
    if is_js:
        lines = text.splitlines(keepends=True)
        changed = False
        result = []
        for line in lines:
            idx = line.find('\\n')
            if idx == -1:
                result.append(line)
                continue
            prefix = line[:idx]
            # Heuristic: if even number of unescaped quotes before \n, we're outside a string.
            if (prefix.count('"') - prefix.count('\\"')) % 2 == 0 and \
                    (prefix.count("'") - prefix.count("\\'")) % 2 == 0 and \
                    prefix.count('`') % 2 == 0:
                new_lines = line.replace('\\n', '\n')
                result.append(new_lines)
                changed = True
            else:
                result.append(line)
        if changed:
            Path(file_path).write_text(''.join(result))
            print(f"==> [mu-agent] Reflex: fixed literal \\n in JS/TS file {file_path}")
            return True

    # Targeted mode: mixed file with a 'line continuation' syntax error.
    # Replace \\n only on lines where it appears outside of a string literal
    # (heuristic: line contains \\n but is not dominated by quotes around it).
    if 'line continuation' not in lint_error:
        return False
    lines = text.splitlines(keepends=True)
    changed = False
    result = []
    for line in lines:
        # Count quotes before the first \\n to decide if we're inside a string.
        idx = line.find('\\n')
        if idx == -1:
            result.append(line)
            continue
        prefix = line[:idx]
        # If the number of unescaped quote chars before \\n is even, we're not
        # inside a string literal — safe to split.
        if (prefix.count('"') - prefix.count('\\"')) % 2 == 0 and \
                (prefix.count("'") - prefix.count("\\'")) % 2 == 0:
            # Replace all \\n in this line with real newlines by splitting.
            new_lines = line.replace('\\n', '\n')
            result.append(new_lines)
            changed = True
        else:
            result.append(line)
    if not changed:
        return False
    Path(file_path).write_text(''.join(result))
    print(f"==> [mu-agent] Reflex: fixed literal \\n (line continuation) in {file_path}")
    return True
