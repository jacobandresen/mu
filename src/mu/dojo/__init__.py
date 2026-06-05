"""The dojo test rig — run mu against the practice problems and learn from it.

This is **harness, not product**: it exercises the shipped `mu` CLI (plan, agent,
iterate, reflect …) against the catalog in ``problems-catalog.json``. It is a
hidden ``mu`` subcommand — ``mu dojo …`` (equivalently ``python -m mu.dojo …``):

    mu dojo measure  p9-vue-todo --runs 5   # N runs from a frozen plan
    mu dojo run      [problem-id]            # one problem, or all
    mu dojo practice --rounds 5             # repeated rounds + learning
    mu dojo fixture  apply p6-rust .         # copy committed fixtures into a dir

It replaced the former ``measure.sh`` / ``sit.sh`` / ``practice.sh`` shell
scripts (see docs/DOJO_PYTHON_PORT.md). Shared plumbing lives in:

- ``env``      — PATH augmentation, archive dir, LM Studio host, the mu command
- ``sessions`` — read finalized sessions out of the archive as dataclasses
"""
