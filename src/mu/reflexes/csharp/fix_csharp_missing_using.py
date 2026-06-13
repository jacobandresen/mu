import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

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
