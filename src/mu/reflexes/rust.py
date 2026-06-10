"""Rust / Cargo reflexes: deterministic post-write fixers for Rust sources and
``Cargo.toml`` manifests. Split out of the monolithic reflexes module so each
language's fixers live together. No logic changes from the original.
"""

import re
from pathlib import Path

from mu.reflexes.core import _fix_duplicate_decls


__all__ = [
    'fix_rust_println_missing_arg',
    'fix_rust_cargo_toml',
    'fix_rust_cargo_bad_dependency',
    'fix_rust_duplicate_use',
    'fix_rust_unbalanced_braces',
    'fix_rust_missing_trait_import',
    'apply_rust_source_reflexes',
]


def fix_rust_println_missing_arg(file_path: str) -> bool:
    """Fix println!/print! calls whose placeholder count doesn't match argument count.

    Models write format strings like `println!("{}")` or `println!("Fib({}) = {}")`
    with too few arguments. When inside a `for var in ...` loop, fills missing args
    with the loop variable (repeated if needed). Generic: any mismatch between `{}`
    count and argument count is a compile error in Rust.
    """
    if not file_path.endswith('.rs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines()
    changed = False
    result = []
    loop_var_stack: list[str] = []

    for line in lines:
        stripped = line.strip()
        m = re.match(r'for\s+(\w+)\s+in\b', stripped)
        if m:
            loop_var_stack.append(m.group(1))

        # Match println!("...") or print!("...") — capture format string and args
        macro_m = re.search(r'\b(println|print)!\s*\(("(?:[^"\\]|\\.)*")(.*)\)', line)
        if macro_m:
            fmt_str = macro_m.group(2)  # includes surrounding quotes
            rest = macro_m.group(3)     # ', arg1, arg2, ...' or ''
            n_placeholders = fmt_str.count('{}')
            existing_args = [a.strip() for a in rest.lstrip(',').split(',') if a.strip()]
            if n_placeholders > len(existing_args) and loop_var_stack:
                var = loop_var_stack[-1]
                all_args = existing_args + [var] * (n_placeholders - len(existing_args))
                new_call = f'{macro_m.group(1)}!({fmt_str}, {", ".join(all_args)})'
                line = line.replace(macro_m.group(0), new_call, 1)
                changed = True

        if stripped == '}' and loop_var_stack:
            loop_var_stack.pop()
        result.append(line)

    if not changed:
        return False
    Path(file_path).write_text('\n'.join(result) + '\n')
    print(f"==> [mu-agent] Reflex: fixed println! missing arg(s) in {file_path}")
    return True


def fix_rust_cargo_toml(file_path: str) -> bool:
    """Regenerate a corrupted Cargo.toml that has merged or duplicate sections.

    The repair model sometimes appends content to Cargo.toml without proper
    separation, producing artifacts like `authors = ["x"][package]` or multiple
    `[package]` headers. Detect these and replace with a minimal valid Cargo.toml.
    """
    if Path(file_path).name.lower() != 'cargo.toml':
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Corruption signals: inline '][', multiple [package] sections, [[package]]
    is_corrupt = (
        re.search(r'\]\[', text) is not None
        or text.count('\n[package]') > 1
        or '[[package]]' in text
        or text.count('[package]') > 1
    )
    if not is_corrupt:
        return False
    # Extract the project name if we can find it
    m = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
    proj = m.group(1) if m else Path(file_path).parent.name or 'app'
    # Detect if there's a src/main.rs or main.rs to set up [[bin]]
    has_src_main = Path(Path(file_path).parent / 'src' / 'main.rs').exists()
    has_root_main = Path(Path(file_path).parent / 'main.rs').exists()
    clean = (
        '[package]\n'
        f'name = "{proj}"\n'
        'version = "0.1.0"\n'
        'edition = "2021"\n'
    )
    if has_root_main and not has_src_main:
        clean += f'\n[[bin]]\nname = "{proj}"\npath = "main.rs"\n'
    Path(file_path).write_text(clean)
    print(f"==> [mu-agent] Reflex: regenerated corrupted Cargo.toml in {file_path}")
    return True


_CARGO_DEP_SECTIONS = ('[dependencies]', '[dev-dependencies]', '[build-dependencies]')
_CARGO_DEP_LINE = re.compile(r'^\s*([A-Za-z0-9_-]+)\s*=\s*["\']([^"\']*)["\']\s*$')


def fix_rust_cargo_bad_dependency(file_path: str) -> bool:
    """Drop `[dependencies]` entries whose value is not a valid version requirement.

    Small models hallucinate dependencies like ``binary = "fib"`` — a value that
    is not a semver requirement — and `cargo` then fails to even parse the
    manifest ("unexpected character 'f' while parsing major version number"),
    blocking the whole build. Only simple ``name = "value"`` lines inside a
    dependency section are removed, and only when the value cannot be a version
    (does not start with a digit or one of ``^ ~ > < = *``). Real deps
    (``serde = "1"``), table-form deps, and ``[package]`` fields are untouched.
    """
    if Path(file_path).name != 'Cargo.toml':
        return False
    try:
        lines = Path(file_path).read_text().splitlines()
    except OSError:
        return False
    out, in_deps, changed = [], False, False
    for line in lines:
        s = line.strip()
        if s.startswith('['):
            in_deps = s in _CARGO_DEP_SECTIONS
            out.append(line)
            continue
        if in_deps:
            m = _CARGO_DEP_LINE.match(line)
            if m and not re.match(r'^[\d*~^<>=]', m.group(2).strip()):
                changed = True
                continue  # drop the bogus dependency line
        out.append(line)
    if not changed:
        return False
    Path(file_path).write_text('\n'.join(out) + '\n')
    print(f"==> [mu-agent] Reflex: dropped invalid Cargo.toml dependency in {file_path}")
    return True


def fix_rust_duplicate_use(file_path: str) -> bool:
    """Remove exact duplicate `use` lines from a Rust source file.

    The model sometimes emits the same `use std::io::{self, Write};` line twice,
    causing E0252 'name defined multiple times'. Dedup in order of first occurrence.
    """
    if not file_path.endswith('.rs'):
        return False
    def _match(line: str):
        s = line.strip()
        return s if s.startswith('use ') else None
    removed = _fix_duplicate_decls(file_path, _match, keepends=True)
    if removed:
        print(f"==> [mu-agent] Reflex: removed duplicate use statement(s) in {file_path}")
    return removed > 0


def fix_rust_unbalanced_braces(file_path: str, build_output: str = '') -> bool:
    """Append or remove closing braces in Rust files with unbalanced brace counts.

    rustc "unclosed delimiter" or "expected `}`" means the file has more `{`
    than `}`. This reflex counts braces (ignoring strings and comments) and
    appends the missing `}` characters.  General: applies to any Rust file.
    """
    if not file_path.endswith('.rs'):
        return False
    if build_output and 'unclosed delimiter' not in build_output and 'expected `}`' not in build_output:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < len(text) and text[i + 1] == '*':
            i += 2
            while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
            continue
        if c == '"':
            i += 1
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '"':
                    break
                i += 1
        elif c == '\'':
            i += 1
            while i < len(text):
                if text[i] == '\\':
                    i += 2
                    continue
                if text[i] == '\'':
                    break
                i += 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    if depth == 0:
        return False
    if depth > 0:
        Path(file_path).write_text(text.rstrip() + '\n' + '}\n' * depth)
        print(f"==> [mu-agent] Reflex: added {depth} missing closing brace(s) to {file_path}")
        return True
    # depth < 0: too many `}` — remove trailing ones
    lines = text.rstrip().splitlines()
    new_lines = list(lines)
    removed = 0
    for idx in range(len(lines) - 1, -1, -1):
        if removed >= abs(depth):
            break
        if new_lines[idx].strip() == '}':
            del new_lines[idx]
            removed += 1
    if not removed:
        return False
    Path(file_path).write_text('\n'.join(new_lines) + '\n')
    print(f"==> [mu-agent] Reflex: removed {removed} extra closing brace(s) from {file_path}")
    return True


def fix_rust_missing_trait_import(file_path: str, build_output: str) -> bool:
    """Add missing trait `use` statements when rustc says 'the trait is in scope'.

    rustc E0599 often says:
      "trait `Write` which provides `flush` is implemented but not in scope;
       perhaps you want to import it: `use std::io::Write;`"
    This reflex extracts the suggested `use` statement and adds it to the file.
    General: driven entirely by the compiler's suggestion, not any specific program.
    """
    if not file_path.endswith('.rs'):
        return False
    if not any(c in build_output for c in ('E0599', 'E0425', 'not in scope', 'not found in this scope')):
        return False
    # Parse suggested `use X::Y;` lines: both inline backtick format and diff-style "N + use ..."
    suggestions = re.findall(r'`(use [^`]+;)`', build_output)
    suggestions += re.findall(r'^\s*\d+\s*\+\s*(use [^;]+;)', build_output, re.MULTILINE)
    if not suggestions:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    to_add = [stmt for stmt in suggestions if stmt not in text]
    if not to_add:
        return False
    lines = text.splitlines()
    # Insert after the last existing use statement
    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('use '):
            insert_at = i + 1
    for stmt in reversed(to_add):
        lines.insert(insert_at, stmt)
    Path(file_path).write_text('\n'.join(lines) + '\n')
    print(f"==> [mu-agent] Reflex: added missing trait import(s) to {file_path}: {to_add}")
    return True


def apply_rust_source_reflexes(file_path: str) -> None:
    """Write-phase .rs chain — preserves the order used in agent.py ~823."""
    if not file_path.endswith('.rs'):
        return
    fix_rust_duplicate_use(file_path)
    fix_rust_println_missing_arg(file_path)
