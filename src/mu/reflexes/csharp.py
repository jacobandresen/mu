"""C# / .NET reflexes: deterministic post-write fixers for C# sources. Split out
of the monolithic reflexes module so each language's fixers live together. No
logic changes from the original.
"""

import re
from pathlib import Path


__all__ = [
    'fix_csharp_verbatim_string_escape',
    'fix_csharp_keyword_prefix_artifacts',
    'fix_csharp_using_order',
    'fix_csharp_duplicate_classes',
    'fix_csharp_missing_using',
    'fix_csharp_missing_braces',
    'apply_csharp_write_reflexes',
    'apply_csharp_repair_reflexes',
]


def fix_csharp_verbatim_string_escape(file_path: str) -> bool:
    """Convert verbatim strings with backslash escapes to regular strings.

    In C# verbatim strings (@"..."), backslash is literal — `\"` does NOT escape
    a quote; it ends the string. Models write `@"{\"key\":value}"` thinking it
    works like a regular string. The fix: drop the `@` prefix so the string
    becomes a regular string where `\"` is valid. The content stays unchanged.
    """
    if not file_path.endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Find @" followed eventually by \" — the verbatim string has invalid escaping.
    # Replace @" with plain " to make it a regular string.
    new_text = re.sub(r'@("(?:[^"\\]|\\.)*")', r'\1', text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: converted verbatim strings to regular strings in {file_path}")
    return True


def fix_csharp_keyword_prefix_artifacts(file_path: str) -> bool:
    """Remove stray 1-2 char prefix artifacts glued to C# keywords at line start.

    Models occasionally emit `tnamespace`, `#class`, etc. — a lone character
    fused to a keyword. The `t` before `namespace` causes CS1513/CS1022.
    Pattern: line starts with 1-2 lowercase letters OR a non-letter char,
    immediately followed (no space) by a known keyword + word boundary.
    """
    if not file_path.endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    kws = (r'namespace|class|struct|interface|enum|public|private|protected|'
           r'internal|using|static|abstract|sealed|partial|record')
    # Match 1-2 lowercase letters OR one symbol, fused directly to a keyword
    pattern = re.compile(r'^(?:[a-z]{1,2}|[^a-zA-Z\s])(' + kws + r')\b', re.MULTILINE)
    new_text = pattern.sub(r'\1', text)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: removed keyword prefix artifact(s) in {file_path}")
    return True


def fix_csharp_using_order(file_path: str) -> bool:
    """Move all `using` directives to the top of a C# source file.

    CS1529 'A using clause must precede all other elements' fires when using
    statements appear after top-level statements, namespace blocks, or class
    definitions. This reflex collects all using lines and re-emits them at the
    very start of the file before any non-using content.
    """
    if not file_path.endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    lines = text.splitlines(keepends=True)
    using_lines = [ln for ln in lines if ln.lstrip().startswith('using ')]
    non_using_lines = [ln for ln in lines if not ln.lstrip().startswith('using ')]
    if not using_lines:
        return False
    # Check if any using is already out of order (appears after non-empty non-using)
    first_non_using = next((i for i, ln in enumerate(lines)
                            if not ln.lstrip().startswith('using ') and ln.strip()), None)
    first_using_after = any(
        i > first_non_using
        for i, ln in enumerate(lines)
        if ln.lstrip().startswith('using ')
    ) if first_non_using is not None else False
    if not first_using_after:
        return False
    new_text = ''.join(using_lines) + ''.join(non_using_lines)
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: moved using statements to top of {file_path}")
    return True


def fix_csharp_duplicate_classes(file_path: str) -> bool:
    """Remove class/struct definitions from a C# file that are already defined in a sibling file.

    Models sometimes copy a class into Program.cs even though the planner created
    a separate file for it (e.g. FibonacciGenerator.cs). The compiler rejects the
    duplicate with CS0101. Generic: checks sibling .cs files for any class/struct
    name that also appears in this file and removes the duplicate block.
    """
    if not file_path.endswith('.cs'):
        return False
    path = Path(file_path)
    try:
        text = path.read_text()
    except OSError:
        return False
    # Collect class/struct names defined in sibling .cs files
    sibling_names: set[str] = set()
    for sib in path.parent.glob('*.cs'):
        if sib == path:
            continue
        try:
            src = sib.read_text()
        except OSError:
            continue
        for m in re.finditer(r'\b(?:class|struct|record)\s+(\w+)', src):
            sibling_names.add(m.group(1))
    if not sibling_names:
        return False
    # Remove any class/struct block defined in this file that's already in a sibling
    changed = False
    for name in sibling_names:
        pattern = re.compile(
            rf'(?m)^[ \t]*(?:(?:public|internal|private|protected|static|sealed|abstract|partial)\s+)*'
            rf'(?:class|struct|record)\s+{re.escape(name)}\b[^{{]*\{{',
        )
        m = pattern.search(text)
        if not m:
            continue
        # Find the matching closing brace via depth tracking.
        start = m.start()
        depth = 0
        end = len(text)
        for i in range(m.end() - 1, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        text = text[:start] + text[end:]
        changed = True
    if not changed:
        return False
    path.write_text(text)
    print(f"==> [mu-agent] Reflex: removed duplicate C# class(es) from {file_path}")
    return True


def fix_csharp_missing_using(file_path: str, build_output: str) -> bool:
    """Add missing `using` directives when CS0246 reports an undefined type/namespace.

    CS0246 fires when a .cs file references a type whose namespace is not imported.
    This reflex searches sibling .cs files (recursively) for the namespace that
    defines the missing type and adds the corresponding `using` directive.
    General: CS0246 on a type that exists elsewhere in the project always means
    a missing using — not a logic error.
    """
    if 'CS0246' not in build_output:
        return False
    if not file_path.lower().endswith('.cs'):
        return False
    # Parse "error CS0246: The type or namespace name 'Foo' could not be found"
    missing_types = set(re.findall(r"CS0246[^']*'(\w+)'", build_output))
    if not missing_types:
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Find namespaces that define these types in sibling .cs files
    proj_root = Path(file_path).parent
    # Walk up to find project root (directory with a .csproj)
    for parent in [proj_root, proj_root.parent, proj_root.parent.parent]:
        if list(parent.glob('*.csproj')):
            proj_root = parent
            break
    to_add: list[str] = []
    for cs_file in proj_root.rglob('*.cs'):
        if cs_file == Path(file_path):
            continue
        try:
            src = cs_file.read_text()
        except OSError:
            continue
        # Extract namespace declarations
        ns_match = re.search(r'(?m)^namespace\s+([\w.]+)', src)
        if not ns_match:
            continue
        ns = ns_match.group(1)
        for typ in list(missing_types):
            if re.search(rf'(?m)^(?:public|internal|private)?\s*(?:class|struct|record|interface|enum)\s+{re.escape(typ)}\b', src):
                using_stmt = f'using {ns};'
                if using_stmt not in text and using_stmt not in to_add:
                    to_add.append(using_stmt)
                missing_types.discard(typ)
    if not to_add:
        return False
    lines = text.splitlines()
    # Insert after the last existing using line
    insert_at = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('using '):
            insert_at = i + 1
    for stmt in reversed(to_add):
        lines.insert(insert_at, stmt)
    Path(file_path).write_text('\n'.join(lines) + '\n')
    print(f"==> [mu-agent] Reflex: added {len(to_add)} missing using(s) to {file_path}: {to_add}")
    return True


def fix_csharp_missing_braces(file_path: str) -> bool:
    """Append missing closing braces to C# files with unbalanced brace counts.

    CS1513 '} expected' means the file has more `{` than `}`. This reflex counts
    braces (ignoring strings and comments) and appends the missing `}` characters.
    General: applies to any C# file, not specific to any program.
    """
    if not file_path.lower().endswith('.cs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Count braces outside strings and single-line comments
    depth = 0
    i = 0
    while i < len(text):
        c = text[i]
        if c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            # Single-line comment — skip to end of line
            while i < len(text) and text[i] != '\n':
                i += 1
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
    # depth < 0: too many `}` — remove trailing standalone `}` lines
    lines = text.rstrip().splitlines()
    new_lines = list(lines)
    removed = 0
    for idx in range(len(lines) - 1, -1, -1):
        if removed >= abs(depth):
            break
        stripped = new_lines[idx].strip()
        if stripped == '}':
            del new_lines[idx]
            removed += 1
    if not removed:
        return False
    Path(file_path).write_text('\n'.join(new_lines) + '\n')
    print(f"==> [mu-agent] Reflex: removed {removed} extra closing brace(s) from {file_path}")
    return True


def apply_csharp_write_reflexes(file_path: str) -> None:
    """Write-phase C# chain — preserves the order used in agent.py ~748."""
    if not file_path.endswith('.cs'):
        return
    fix_csharp_keyword_prefix_artifacts(file_path)
    fix_csharp_verbatim_string_escape(file_path)
    fix_csharp_using_order(file_path)
    fix_csharp_missing_braces(file_path)
    fix_csharp_duplicate_classes(file_path)


def apply_csharp_repair_reflexes(file_path: str, test_output: str = '') -> None:
    """Repair-phase C# chain — preserves the order used in agent.py ~1333."""
    if not file_path.endswith('.cs'):
        return
    fix_csharp_keyword_prefix_artifacts(file_path)
    fix_csharp_verbatim_string_escape(file_path)
    fix_csharp_using_order(file_path)
    fix_csharp_missing_braces(file_path)
    if test_output:
        fix_csharp_missing_using(file_path, test_output)
