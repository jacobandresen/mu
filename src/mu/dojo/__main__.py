"""``python -m mu.dojo …`` — same parser as ``mu dojo`` (see cli.py)."""

import sys

from .cli import main

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
