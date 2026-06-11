"""Regression test: fix_inline_recipe / fix_makefile_recipe_is_prerequisite_list
must not oscillate when applied back-to-back.

Root cause: fix_inline_recipe's prerequisite-list guard previously used `declared`
(actual target names in the file) while fix_makefile_recipe_is_prerequisite_list
uses `declared | _KNOWN_TARGETS`. When 'install'/'test' are in _KNOWN_TARGETS but
not declared as targets, the two reflexes undid each other on every repair pass.

Fix: extend the guard in fix_inline_recipe to use `declared | _KNOWN_TARGETS`.
"""

import tempfile
from pathlib import Path

from mu.reflexes.makefile import fix_inline_recipe, fix_makefile_recipe_is_prerequisite_list


def _write(tmp: Path, content: str) -> Path:
    p = tmp / 'Makefile'
    p.write_text(content)
    return p


def test_no_oscillation_known_targets_not_declared():
    """all: install test — 'install' and 'test' are _KNOWN_TARGETS but not
    declared as explicit targets. Previously caused infinite oscillation."""
    content = "all: install test\n\ninstall:\n\tpip install -r requirements.txt\n\ntest:\n\tpytest\n"
    with tempfile.TemporaryDirectory() as tmp:
        p = _write(Path(tmp), content)
        before = p.read_text()
        fix_inline_recipe(str(p))
        after_1 = p.read_text()
        fix_makefile_recipe_is_prerequisite_list(str(p))
        after_2 = p.read_text()
        fix_inline_recipe(str(p))
        after_3 = p.read_text()
        # The file must stabilize — after_2 == after_3 (no further change)
        assert after_2 == after_3, (
            f"Oscillation detected:\nafter fix_makefile_recipe_is_prerequisite_list:\n{after_2}\n"
            f"after fix_inline_recipe again:\n{after_3}"
        )


def test_no_oscillation_inline_known_target():
    """all: install test written inline (space after colon, no newline recipe)."""
    content = "all: install test\n\ninstall:\n\techo done\n\ntest:\n\tpytest\n"
    with tempfile.TemporaryDirectory() as tmp:
        p = _write(Path(tmp), content)
        # Apply the pair 3 times — must stabilize by second application
        for _ in range(3):
            fix_makefile_recipe_is_prerequisite_list(str(p))
            fix_inline_recipe(str(p))
        s1 = p.read_text()
        fix_makefile_recipe_is_prerequisite_list(str(p))
        fix_inline_recipe(str(p))
        s2 = p.read_text()
        assert s1 == s2, "Not idempotent after stabilization"


def test_fix_inline_recipe_still_splits_compiler_calls():
    """fix_inline_recipe must still split genuine inline compiler recipes."""
    content = "all: gcc -o app main.c\n"
    with tempfile.TemporaryDirectory() as tmp:
        p = _write(Path(tmp), content)
        changed = fix_inline_recipe(str(p))
        result = p.read_text()
        assert changed, "Should have split the compiler inline recipe"
        assert '\tall:' not in result
        assert '\tgcc' in result


def test_fix_inline_recipe_leaves_declared_prereqs_alone():
    """all: build test — both are declared targets — must not be split."""
    content = "all: build test\n\nbuild:\n\tgcc -o app main.c\n\ntest:\n\t./app\n"
    with tempfile.TemporaryDirectory() as tmp:
        p = _write(Path(tmp), content)
        before = p.read_text()
        fix_inline_recipe(str(p))
        assert p.read_text() == before, "Should not modify a declared-targets prerequisite list"
