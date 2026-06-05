"""``python -m mu.dojo <command>`` — the dojo rig entry point.

A thin dispatcher mirroring ``mu.fixtures``' CLI style. Configuration stays in
environment variables (N, MU_SEED, ROUNDS, SKIP_*, MU_ROUTE …) for parity with
the shell scripts and the existing docs; the positional arg is just the command
and, where relevant, a problem id.
"""

import sys


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ''
    if cmd == 'measure':
        if len(argv) < 2:
            sys.exit("usage: python -m mu.dojo measure <problem-id>   (N=, MU_SEED=, REGEN= via env)")
        from . import measure
        return measure.run(argv[1])
    # 'run' and 'practice' land in later phases (docs/DOJO_PYTHON_PORT.md).
    sys.exit("usage: python -m mu.dojo measure <problem-id>")


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
