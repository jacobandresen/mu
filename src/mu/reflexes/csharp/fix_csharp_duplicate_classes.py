import re
from pathlib import Path
from mu.reflexes.core import noted

from ._common import *  # noqa: F401,F403

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
