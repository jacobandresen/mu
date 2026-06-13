"""Guard: every reflex name referenced in agent.py must resolve in its
namespace.

2026-06-13: fix_csharp_test_program_conflict and fix_python_unindented_body
were wired into agent.py call sites but never added to its import block. The
unit tests passed (they import the reflexes from mu.reflexes directly), so
the NameError only fired at runtime inside reapply() — crashing the test-gate
repair loop for every problem and wasting a full 8h collection run. This
test reproduces that failure statically: it flags a reflex used as a call
OR passed by reference (e.g. into _fired/run_reflexes) that isn't bound.
"""

import ast

import mu.agent


def test_all_referenced_reflexes_are_importable():
    src = open(mu.agent.__file__).read()
    tree = ast.parse(src)
    # Names defined locally in agent.py (defs + assignments) are fine even if
    # not imported — collect them so the guard only flags genuinely unbound
    # reflex references.
    local = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}

    referenced: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                and (node.id.startswith('fix_') or node.id.startswith('apply_'))):
            referenced.add(node.id)

    missing = sorted(n for n in referenced
                     if n not in local and not hasattr(mu.agent, n))
    assert not missing, f"reflex(es) used in agent.py but not imported: {missing}"
