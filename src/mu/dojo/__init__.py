"""The dojo test rig — run mu against the practice problems and learn from it.

This is **harness, not product**: it exercises the shipped `mu` CLI (plan, agent,
iterate, reflect …) against the catalog in ``problems-catalog.json``, so it lives
off that surface, under ``python -m mu.dojo`` (like ``python -m mu.fixtures``):

    python -m mu.dojo measure  p9-vue-todo     # N runs from a frozen plan
    python -m mu.dojo run      [problem-id]     # one problem, or all
    python -m mu.dojo practice                  # repeated rounds + learning

It replaces the former ``measure.sh`` / ``sit.sh`` / ``practice.sh`` shell
scripts (see docs/DOJO_PYTHON_PORT.md). Shared plumbing lives in:

- ``env``      — PATH augmentation, archive dir, LM Studio host, the mu command
- ``sessions`` — read finalized sessions out of the archive as dataclasses
"""
