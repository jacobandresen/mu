"""Idempotency tests for scan/file reflexes.

Each reflex that operates on a single file should be *content idempotent*:
applying it twice must not further modify the file. This test loads all reflexes
with ``trigger=='scan'`` and ``scope=='file'`` from the registry, runs them on a
set of fixture files, and asserts that the second application leaves the file
content unchanged.
"""

import shutil
import tempfile
from pathlib import Path

from mu.reflexes.registry import discover
from mu.reflexes.core import fix_json_unclosed_brackets  # noqa: F401 (example import)

# Load the reflex functions that are scan/file
# Build list of (id, function) for scan/file reflexes, skipping those that take no arguments.
REFLEXES = [
    (rec.id, globals().get(rec.id) or __import__(f"mu.reflexes.{rec.toolchain}", fromlist=[rec.id]).__dict__[rec.id])
    for rec in discover()
    if rec.trigger == "scan" and rec.scope == "file" and (globals().get(rec.id) or __import__(f"mu.reflexes.{rec.toolchain}", fromlist=[rec.id]).__dict__[rec.id]).__code__.co_argcount > 0
]

FIXTURE_DIR = Path(__file__).with_name("fixtures")


def _apply_reflex(fn, path: Path) -> bool:
    """Apply ``fn`` to ``path``.

    Returns ``True`` if the file content changed.
    """
    before = path.read_bytes()
    # Most reflexes accept a Path argument; they may also accept ``file_path`` name.
    # We use positional argument.
    # Many reflexes expect a string path; convert safely.
    try:
        fn(str(path))
    except TypeError:
        # Fallback for reflexes that accept Path objects.
        fn(path)
    after = path.read_bytes()
    return before != after


def test_scan_file_idempotency():
    exercised = 0
    for rec_id, fn in REFLEXES:
        # Find a fixture that the reflex is expected to handle based on its name.
        # Simple heuristic: if the reflex name contains a keyword present in a fixture filename.
        candidate = None
        for fixture in FIXTURE_DIR.iterdir():
            if fixture.is_file() and any(k in rec_id for k in fixture.stem.split('_')):
                candidate = fixture
                break
        if not candidate:
            # fallback: try any fixture
            candidate = next(FIXTURE_DIR.iterdir())
        # Copy fixture to temp location
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td) / candidate.name
            shutil.copy2(candidate, temp_path)
            changed = _apply_reflex(fn, temp_path)
            if not changed:
                # Reflex did not fire; skip idempotency check
                continue
            exercised += 1
            # Apply second time and ensure no further change
            changed2 = _apply_reflex(fn, temp_path)
            assert not changed2, f"Reflex {rec_id} not idempotent on {candidate.name}"
    print(f"Exercised reflex count: {exercised}")
    assert exercised > 0, "No reflexes exercised; fixtures may be missing"
