"""Shared helpers and constants for the csharp reflexes."""

import re
from pathlib import Path
from mu.reflexes.core import noted


_CS_SIG_RE = re.compile(
    r'^\s*(?:(?:public|private|protected|internal|static|async|override|'
    r'virtual|sealed)\s+)+[\w<>\[\],\s.?]+?\b\w+\s*\([^)]*\)\s*\{?\s*$')


_CS_ATTR_RE = re.compile(r'^\s*\[[\w()", =.]+\]\s*$')


# A top-level type declaration (captures the name): class/struct/record Foo …
_TYPE_DECL_RE = re.compile(
    r'(?m)^[ \t]*(?:(?:public|internal|private|protected|static|sealed|abstract|partial)\s+)*'
    r'(?:class|struct|record)\s+(\w+)')


def _cs_source_files(project_dir: str) -> list[Path]:
    """All project .cs files, skipping build output (obj/bin)."""
    return [p for p in Path(project_dir).rglob('*.cs')
            if not any(s in p.parts for s in ('obj', 'bin'))]


def _is_test_path(path: Path) -> bool:
    """True for a test project/file — the part that *references* shared types and
    must never own them (so the cross-stage guard keeps the backend definition)."""
    return any('test' in part.lower() for part in path.parts)


def _strip_type_block(text: str, name: str) -> tuple[str, bool]:
    """Remove the first top-level ``class/struct/record <name> { … }`` block from
    *text* by brace-depth tracking (and a trailing newline). Returns
    ``(new_text, removed)``. Positional records with no body (``record X(…);``) are
    left untouched — they have no brace block to balance."""
    pat = re.compile(
        rf'(?m)^[ \t]*(?:(?:public|internal|private|protected|static|sealed|abstract|partial)\s+)*'
        rf'(?:class|struct|record)\s+{re.escape(name)}\b[^{{;]*\{{')
    m = pat.search(text)
    if not m:
        return text, False
    start, depth, end = m.start(), 0, len(text)
    for i in range(m.end() - 1, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    while end < len(text) and text[end] in '\r\n':
        end += 1
    return text[:start] + text[end:], True


__all__ = ['_CS_SIG_RE', '_CS_ATTR_RE', '_TYPE_DECL_RE',
           '_cs_source_files', '_is_test_path', '_strip_type_block']
