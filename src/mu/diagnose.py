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

To teach it a new error shape, add one ``_rule(...)`` to ``_RULES`` below: a
regex with **named** groups and a one-line ``render`` that names the entity and
the error class but does NOT prescribe the fix (the model decides that).
"""

import re
from typing import Callable, NamedTuple, Optional


class _Rule(NamedTuple):
    """One error grammar: a compiled pattern and how to phrase a match."""
    pattern: re.Pattern
    render: Callable[[re.Match], str]


def _rule(regex: str, render: Callable[[re.Match], str], flags: int = 0) -> _Rule:
    return _Rule(re.compile(regex, flags), render)


def _clip(text: str, limit: int = 90) -> str:
    """Trim a captured compiler message to keep the hint to one tidy line."""
    return text.strip()[:limit]


# Error grammars, grouped by toolchain. Tried top-to-bottom against each line;
# the first match wins. Named groups keep the render functions readable.
_RULES: list[_Rule] = [
    # ── Python: CPython syntax errors, pyflakes/ruff, runtime tracebacks ──
    _rule(r"^(?P<file>.+?):(?P<line>\d+):\d+:\s*(?:E999 )?(?:invalid-syntax: )?"
          r"(?P<msg>unterminated (?:string|triple-quoted string) literal)",
          lambda m: f"{m['file']}:{m['line']}: {m['msg']} — close the quote on that line",
          re.I),
    _rule(r"^(?P<file>.+?):(?P<line>\d+):\d+:?\s*(?:F821 )?undefined name [`'](?P<name>[^`']+)[`']",
          lambda m: f"{m['file']}:{m['line']}: undefined name '{m['name']}' (missing import or definition)",
          re.I),
    _rule(r"^\s*File \"(?P<file>.+?)\", line (?P<line>\d+)",
          lambda m: f"{m['file']}:{m['line']}: see traceback below"),
    _rule(r"^(?:E\s+)?ModuleNotFoundError: No module named ['\"](?P<module>[^'\"]+)['\"]",
          lambda m: f"ModuleNotFoundError: '{m['module']}' — import it or add it to requirements/install step"),
    _rule(r"^(?:E\s+)?NameError: name ['\"](?P<name>[^'\"]+)['\"] is not defined",
          lambda m: f"NameError: '{m['name']}' is not defined"),
    _rule(r"^(?:E\s+)?(?:ImportError|AttributeError): (?P<msg>.+)$",
          lambda m: _clip(m['msg'])),
    _rule(r"^(?:E\s+)?(?P<kind>SyntaxError|IndentationError|TabError): (?P<msg>.+)$",
          lambda m: f"{m['kind']}: {_clip(m['msg'])}"),
    _rule(r"^E\s+(?P<expr>assert\b.+)$",
          lambda m: f"failing assertion: {_clip(m['expr'])}"),

    # ── JavaScript / Node / Jest runtime ──
    # Jest prints these indented under a ``●`` test header, so allow leading
    # whitespace (the matcher uses .search). Covers Python's TypeError/
    # ReferenceError too — same shape, same useful hint.
    _rule(r"(?:^|\s)(?P<kind>TypeError|ReferenceError): (?P<msg>.+)$",
          lambda m: f"{m['kind']}: {_clip(m['msg'])}"),
    _rule(r"No matching version found for (?P<pkg>\S+)",
          lambda m: f"package.json: no such package version '{m['pkg']}' "
                    f"(a Node builtin or a bad version) — fix or remove it"),

    # ── Rust / cargo ──
    _rule(r"failed to parse the version requirement [`'](?P<version>[^`']+)[`'] "
          r"for dependency [`'](?P<dep>[^`']+)[`']",
          lambda m: f"Cargo.toml: dependency '{m['dep']}' has an invalid version "
                    f"'{m['version']}' — remove that dependency line"),
    _rule(r"^error\[E\d+\]:\s*(?P<phrase>cannot find \w+ [`'][^`']+[`'] in this scope)",
          lambda m: m['phrase'],
          re.I),
    _rule(r"^error\[(?P<code>E\d+)\]:\s*(?P<msg>.+)$",
          lambda m: f"rustc {m['code']}: {_clip(m['msg'])}"),

    # ── Go ──
    _rule(r"undefined:\s*(?P<symbol>\w+)",
          lambda m: f"Go: undefined symbol '{m['symbol']}' (missing import or declaration)"),
    _rule(r'"(?P<import>[^"]+)" imported and not used',
          lambda m: f"Go: import '{m['import']}' is unused — remove it"),
    _rule(r"^(?P<file>\S+?\.go):(?P<line>\d+):\d+:\s*syntax error:\s*(?P<msg>.+)$",
          lambda m: f"{m['file']}:{m['line']}: Go syntax error: {_clip(m['msg'])}"),

    # ── C# / MSBuild ──
    _rule(r"error (?P<code>CS\d+):\s*(?P<msg>.+?)(?:\s*\[|$)",
          lambda m: f"{m['code']}: {_clip(m['msg'])}"),
    _rule(r"MSBUILD\s*:\s*error (?P<code>MSB\d+):\s*(?P<msg>.+?)(?:\s*\[|$)",
          lambda m: f"MSBuild {m['code']}: {_clip(m['msg'])}",
          re.I),

    # ── Go (extended) ──
    _rule(r"cannot use (?P<expr>.+?) \((?:type|variable of type) .+?\) as (?:type )?(?P<typ>\S+)",
          lambda m: f"Go: type error — cannot use {_clip(m['expr'], 40)} as {m['typ']}",
          re.I),
    _rule(r"not enough arguments in call to (?P<func>\S+)",
          lambda m: f"Go: not enough arguments in call to '{m['func']}'",
          re.I),
    _rule(r"too many arguments in call to (?P<func>\S+)",
          lambda m: f"Go: too many arguments in call to '{m['func']}'",
          re.I),
    _rule(r"(?P<file>\S+?\.go):(?P<line>\d+):\d+:\s*(?P<name>\w+) declared (?:and|but) not used",
          lambda m: f"{m['file']}:{m['line']}: '{m['name']}' declared but not used — remove it"),
    _rule(r"^--- FAIL:\s*(?P<test>\w+)",
          lambda m: f"Go test failed: {m['test']}"),

    # ── Go: no test files ──
    _rule(r"\[no test files\]",
          lambda m: "Go: no test files found — add *_test.go files or fix package path"),

    # ── Go modules ──
    _rule(r"go: errors parsing go\.mod",
          lambda m: "go.mod is malformed — fix or regenerate it (go mod init/tidy)"),

    # ── JavaScript / npm ──
    _rule(r"npm error Missing script:\s*[\"']?(?P<script>[^\"'\s]+)[\"']?",
          lambda m: f"npm: missing script '{m['script']}' — add it to package.json or fix Makefile test target",
          re.I),
    _rule(r"Jest encountered an unexpected token",
          lambda m: "Jest: ESM/CJS parse error — add Babel transform or jest.config transform for ES modules"),
    _rule(r"Cannot find module ['\"](?P<mod>[^'\"]+)['\"] from",
          lambda m: f"Jest: cannot find module '{m['mod']}' — run npm install or add it to package.json"),
    _rule(r"●\s+process\.exit called with ['\"](?P<code>\d+)['\"]",
          lambda m: f"Jest: test code called process.exit({m['code']}) — remove exit call or catch it"),
    _rule(r"npm error code (?P<code>EJSONPARSE|E\w+)",
          lambda m: f"npm error {m['code']}: package.json is malformed — fix JSON syntax"),

    # ── make ──
    _rule(r"^(?:.*\bmake.*?:\s*)?\*\*\* (?P<msg>missing separator.*)$",
          lambda m: f"Makefile: {_clip(m['msg'], 80)} — recipe lines must start with a TAB",
          re.I),
    _rule(r"\*\*\* No rule to make target ['`](?P<target>[^'`]+)['`]",
          lambda m: f"Makefile: no rule to make target '{m['target']}'"),
    _rule(r"(?:clang|gcc|cc).*?no such file or directory:\s*['\"]?(?P<file>[^'\"]+)['\"]?",
          lambda m: f"C compiler: source file '{m['file']}' not found — add it or fix the Makefile",
          re.I),
    _rule(r"(?:make:\s*)?(?P<cmd>[\w.\-/]+): [Cc]ommand not found",
          lambda m: f"command not found: '{m['cmd']}' — a typo, an uninstalled tool, "
                    f"or a devDependency binary that needs npx"),

    # ── generic test assertion (jest/dotnet/CTest 'Expected vs Actual') ──
    _rule(r"^\s*Expected:\s*(?P<exp>.+)$",
          lambda m: f"output assertion failed — expected: {_clip(m['exp'], 60)}"),
    # vitest / jest fluent assertion: "expected 'X' to contain 'Y'"
    _rule(r"expected (?P<a>.+?) to (?P<rel>contain|be|equal|match|include|have) (?P<b>.+?)\s*$",
          lambda m: f"assertion failed: expected {_clip(m['a'], 40)} to {m['rel']} {_clip(m['b'], 40)}",
          re.I),
]


def _hint_for_line(line: str) -> Optional[str]:
    """Return the FOCUS phrase for the first rule that matches *line*, or None."""
    for rule in _RULES:
        match = rule.pattern.search(line)
        if match is None:
            continue
        try:
            return rule.render(match)
        except (IndexError, AttributeError):
            return None
    return None


def distill_test_errors(output: str, max_hints: int = 3) -> str:
    """Return a short ``FOCUS`` block naming the first actionable error(s), or ''.

    Scans *output* line by line, collecting up to *max_hints* distinct hints from
    the known error grammars. Returns '' when nothing matches, so callers can
    prepend the result unconditionally without altering behavior on unrecognized
    output.
    """
    hints: list[str] = []
    for line in (output or '').splitlines():
        hint = _hint_for_line(line.rstrip())
        if hint and hint not in hints:
            hints.append(hint)
            if len(hints) >= max_hints:
                break

    if not hints:
        return ''
    if len(hints) == 1:
        return f"FOCUS (most likely cause): {hints[0]}"
    bullets = '\n'.join(f"  - {h}" for h in hints)
    return "FOCUS (most likely causes, in order):\n" + bullets
