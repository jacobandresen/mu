"""One-off refactor helper: move named top-level defs/assignments out of
src/mu/reflexes/__init__.py into a per-language module, verbatim.

Usage: python scripts/_extract_reflexes.py <module> <name1> <name2> ...
Reads HEADER_<module>.txt for the module's docstring+imports preamble.
Writes src/mu/reflexes/<module>.py and rewrites __init__.py with the named
blocks removed. Pure move: source segments are copied byte-for-byte.
"""
import ast
import sys
from pathlib import Path

INIT = Path("src/mu/reflexes/__init__.py")


def main():
    module = sys.argv[1]
    names = set(sys.argv[2:])
    src = INIT.read_text()
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)

    spans = []  # (start_idx, end_idx_exclusive, name)
    for node in tree.body:
        nm = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nm = node.name
        elif isinstance(node, ast.Assign):
            tgts = [t.id for t in node.targets if isinstance(t, ast.Name)]
            nm = tgts[0] if tgts else None
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            nm = node.target.id
        if nm in names:
            start = node.lineno - 1  # 0-based, inclusive
            end = node.end_lineno     # exclusive in 0-based since end_lineno is 1-based last line
            spans.append((start, end, nm))

    found = {s[2] for s in spans}
    missing = names - found
    if missing:
        sys.exit(f"ERROR: names not found as top-level nodes: {sorted(missing)}")

    spans.sort()
    extracted = []
    for start, end, nm in spans:
        extracted.append("".join(lines[start:end]))

    header = Path(f"scripts/HEADER_{module}.txt").read_text()
    body = "\n\n".join(seg.rstrip("\n") for seg in extracted) + "\n"
    Path(f"src/mu/reflexes/{module}.py").write_text(header + body)

    # Remove spans from init, highest-first to keep indices valid.
    keep = list(lines)
    for start, end, _ in sorted(spans, reverse=True):
        del keep[start:end]
    INIT.write_text("".join(keep))
    print(f"moved {len(spans)} block(s) into reflexes/{module}.py")


if __name__ == "__main__":
    main()
