"""Repair-loop sensor: distill raw test/lint output into a one-line FOCUS hint.

The repair loop feeds a small model up to ~60 lines of compiler/test output and
asks for one targeted edit. With an 8k context that is a lot of noise to wade
through, and weak models latch onto the wrong line. Compiler and linter output
is strongly structured, though — ``file:line:col: message`` grammars — so we can
extract the first actionable *entity* (the offending symbol, file, and error
class) deterministically and lead the repair prompt with it.

This is a *sensor* (percept), not a reflex: it observes and summarizes, it does
not change any file. It is deliberately conservative — only high-confidence,
well-known error shapes produce a hint; anything unrecognized yields ``''`` and
the repair prompt is unchanged. No ML, no dependency: the structure is already
in the text, and a regex extracts it at 100% precision for free.
"""

import re

# Each entry: (compiled pattern, formatter). Patterns are matched per line, in
# file order; the first few distinct messages become the FOCUS hint. Formatters
# turn match groups into a short, location-anchored phrase — they name the entity
# and the error class WITHOUT prescribing the fix (the model decides that).
_DIAGNOSERS: list[tuple[re.Pattern, object]] = [
    # ── Python: CPython syntax errors + pyflakes/ruff + runtime tracebacks ──
    (re.compile(r'^(.+?):(\d+):\d+:\s*(?:E999 )?(?:invalid-syntax: )?'
                r'(unterminated (?:string|triple-quoted string) literal)', re.I),
     lambda m: f"{m.group(1)}:{m.group(2)}: {m.group(3)} — close the quote on that line"),
    (re.compile(r"^(.+?):(\d+):\d+:?\s*(?:F821 )?undefined name [`']([^`']+)[`']", re.I),
     lambda m: f"{m.group(1)}:{m.group(2)}: undefined name '{m.group(3)}' (missing import or definition)"),
    (re.compile(r"^\s*File \"(.+?)\", line (\d+)"),
     lambda m: f"{m.group(1)}:{m.group(2)}: see traceback below"),
    (re.compile(r"^(?:E\s+)?ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"),
     lambda m: f"ModuleNotFoundError: '{m.group(1)}' — import it or add it to requirements/install step"),
    (re.compile(r"^(?:E\s+)?NameError: name ['\"]([^'\"]+)['\"] is not defined"),
     lambda m: f"NameError: '{m.group(1)}' is not defined"),
    (re.compile(r"^(?:E\s+)?(?:ImportError|AttributeError): (.+)$"),
     lambda m: f"{m.group(1).strip()[:90]}"),
    (re.compile(r"^(?:E\s+)?(SyntaxError|IndentationError|TabError): (.+)$"),
     lambda m: f"{m.group(1)}: {m.group(2).strip()[:90]}"),
    (re.compile(r"^E\s+(assert\b.+)$"),
     lambda m: f"failing assertion: {m.group(1).strip()[:90]}"),
    # ── Rust / cargo ──
    (re.compile(r"failed to parse the version requirement [`']([^`']+)[`'] "
                r"for dependency [`']([^`']+)[`']"),
     lambda m: f"Cargo.toml: dependency '{m.group(2)}' has an invalid version '{m.group(1)}' — remove that dependency line"),
    (re.compile(r"^error\[E\d+\]:\s*(cannot find \w+ [`'][^`']+[`'] in this scope)", re.I),
     lambda m: f"{m.group(1)}"),
    (re.compile(r"^error\[(E\d+)\]:\s*(.+)$"),
     lambda m: f"rustc {m.group(1)}: {m.group(2).strip()[:90]}"),
    # ── Go ──
    (re.compile(r"undefined:\s*(\w+)"),
     lambda m: f"Go: undefined symbol '{m.group(1)}' (missing import or declaration)"),
    (re.compile(r'"([^"]+)" imported and not used'),
     lambda m: f"Go: import '{m.group(1)}' is unused — remove it"),
    # ── C# / MSBuild ──
    (re.compile(r"error (CS\d+):\s*(.+?)(?:\s*\[|$)"),
     lambda m: f"{m.group(1)}: {m.group(2).strip()[:90]}"),
    # ── make ──
    (re.compile(r"^(?:.*\bmake.*?:\s*)?\*\*\* (missing separator.*)$", re.I),
     lambda m: f"Makefile: {m.group(1).strip()[:80]} — recipe lines must start with a TAB"),
    (re.compile(r"\*\*\* No rule to make target ['`]([^'`]+)['`]"),
     lambda m: f"Makefile: no rule to make target '{m.group(1)}'"),
]


def distill_test_errors(output: str, max_hints: int = 3) -> str:
    """Return a short ``FOCUS`` block naming the first actionable error(s), or ''.

    Scans *output* line by line, collecting up to *max_hints* distinct hints from
    the known error grammars. Returns '' when nothing matches, so callers can
    prepend the result unconditionally without altering behavior on unrecognized
    output.
    """
    if not output:
        return ''
    hints: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        line = line.rstrip()
        for pat, fmt in _DIAGNOSERS:
            m = pat.search(line)
            if not m:
                continue
            try:
                hint = fmt(m)
            except (IndexError, AttributeError):
                continue
            if hint and hint not in seen:
                seen.add(hint)
                hints.append(hint)
            break  # one hint per line
        if len(hints) >= max_hints:
            break
    if not hints:
        return ''
    if len(hints) == 1:
        return f"FOCUS (most likely cause): {hints[0]}"
    bullets = '\n'.join(f"  - {h}" for h in hints)
    return "FOCUS (most likely causes, in order):\n" + bullets
