"""Promote an internal type exposed by a public signature (plan S2 / Step 0.3).

**CS0053** — "inconsistent accessibility: return type/parameter X is less accessible
than method Y" — fires when a ``public`` API surface (a minimal-API handler, a
controller action, a public property) returns or takes a type the writer declared
``internal``. p10's third error class (×8).

Conservative fix: a type **explicitly** declared ``internal class/struct/record T``
that appears in a ``public`` member signature anywhere in the project is raised to
``public``. Types with no explicit modifier are left alone (a no-modifier *nested*
type is private by intent, and promoting blindly is riskier than the error it
fixes). Idempotent; touches only the one ``internal`` keyword on the declaration.
"""
import re
from pathlib import Path

from mu.reflexes.core import noted  # noqa: F401

from ._common import _cs_source_files

# `internal` (optionally with other modifiers) on a class/struct/record decl.
_INTERNAL_DECL = re.compile(
    r'(?m)^([ \t]*)((?:(?:static|sealed|abstract|partial)\s+)*)internal(\s+)'
    r'((?:(?:static|sealed|abstract|partial)\s+)*(?:class|struct|record)\s+(\w+))')

# A public member whose signature mentions a type name (return type or parameter).
_PUBLIC_SIG = re.compile(r'(?m)^\s*public\s+[^\n;{]*')


def fix_csharp_public_signature_accessibility(project_dir: str = '.') -> bool:
    """Raise an ``internal`` type to ``public`` when a ``public`` signature exposes
    it. Returns True if any declaration changed."""
    files = _cs_source_files(project_dir)
    if not files:
        return False
    texts: dict[Path, str] = {}
    internal_types: dict[str, Path] = {}
    public_sig_blob = []
    for f in files:
        try:
            t = f.read_text(errors='ignore')
        except OSError:
            continue
        texts[f] = t
        for m in _INTERNAL_DECL.finditer(t):
            internal_types[m.group(5)] = f
        public_sig_blob.extend(_PUBLIC_SIG.findall(t))

    if not internal_types:
        return False
    sigs = '\n'.join(public_sig_blob)
    exposed = {name for name in internal_types
               if re.search(rf'\b{re.escape(name)}\b', sigs)}
    if not exposed:
        return False

    changed = False
    for f, t in texts.items():
        new = t
        for name in exposed:
            if internal_types.get(name) != f:
                continue
            new = _INTERNAL_DECL.sub(
                lambda m: (m.group(0) if m.group(5) != name
                           else f"{m.group(1)}{m.group(2)}public{m.group(3)}{m.group(4)}"),
                new)
        if new != t:
            f.write_text(new)
            changed = True
            print(f"==> [mu-agent] Reflex: raised internal type(s) exposed by a "
                  f"public signature to public in {f}")
    return changed
