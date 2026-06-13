"""Shared helpers and constants for the python reflexes."""

import re
from pathlib import Path


_PY_STDLIB_IMPORTS = {
    'sqlite3': 'import sqlite3',
    'json': 'import json',
    'os': 'import os',
    'sys': 'import sys',
    're': 'import re',
    'math': 'import math',
    'random': 'import random',
    'datetime': 'from datetime import datetime',
    'threading': 'import threading',
    'subprocess': 'import subprocess',
    'pathlib': 'from pathlib import Path',
    'collections': 'import collections',
    'itertools': 'import itertools',
    'functools': 'import functools',
    'typing': 'from typing import List, Dict, Optional',
    'dataclasses': 'from dataclasses import dataclass',
    'abc': 'from abc import ABC, abstractmethod',
    'uuid': 'import uuid',
    'hashlib': 'import hashlib',
    'base64': 'import base64',
    'copy': 'import copy',
    'time': 'import time',
    'logging': 'import logging',
    # Common third-party frameworks that appear without imports
    'Flask': 'from flask import Flask',
    'request': 'from flask import request',
    'jsonify': 'from flask import jsonify',
}


def _sibling_py_sources(file_path: str) -> dict[str, str]:
    """Return {stem: source} for non-test .py modules importable beside file_path.

    Looks in the file's own directory and, when it sits in a ``tests``/``test``
    subdirectory, the parent (project root) too — the standard pytest layout is
    ``root/main.py`` + ``root/tests/test_main.py``, where the implementation
    module a test needs to import lives one level up, not beside the test. Closer
    directories win on a stem clash.
    """
    fp = Path(file_path)
    dirs = [fp.parent]
    if fp.parent.name.lower() in ('tests', 'test'):
        dirs.append(fp.parent.parent)
    sources: dict[str, str] = {}
    for d in dirs:
        for p in d.glob('*.py'):
            if p.stem == fp.stem or p.stem.startswith('test_') or p.stem in sources:
                continue
            try:
                sources[p.stem] = p.read_text()
            except OSError:
                continue
    return sources


def _insert_py_imports(file_path: str, stmts: list[str]) -> None:
    """Insert import statements after the last existing import line."""
    lines = Path(file_path).read_text().splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith(('import ', 'from ')):
            insert_at = i + 1
        elif line and not line.startswith('#') and insert_at > 0:
            break
    for stmt in reversed(stmts):
        lines.insert(insert_at, stmt)
    Path(file_path).write_text('\n'.join(lines) + '\n')


_STDLIB_MODULES = {
    'os', 'sys', 're', 'json', 'math', 'time', 'datetime', 'pathlib',
    'collections', 'itertools', 'functools', 'typing', 'io', 'abc',
    'random', 'string', 'struct', 'copy', 'enum', 'dataclasses',
    'subprocess', 'threading', 'multiprocessing', 'socket', 'http',
    'urllib', 'hashlib', 'base64', 'uuid', 'logging', 'unittest',
    'contextlib', 'weakref', 'gc', 'inspect', 'importlib', 'pkgutil',
    'ast', 'dis', 'pickle', 'shelve', 'csv', 'sqlite3', 'argparse',
    'shutil', 'tempfile', 'glob', 'fnmatch', 'stat', 'platform',
    'traceback', 'warnings', 'textwrap', 'pprint', 'decimal', 'fractions',
}


_PIP_NAME: dict[str, str] = {
    'flask_sqlalchemy': 'flask-sqlalchemy',
    'flask_migrate': 'flask-migrate',
    'flask_login': 'flask-login',
    'flask_cors': 'flask-cors',
    'flask_restful': 'flask-restful',
    'dotenv': 'python-dotenv',
    'cv2': 'opencv-python',
    'PIL': 'Pillow',
    'sklearn': 'scikit-learn',
    'bs4': 'beautifulsoup4',
    'yaml': 'pyyaml',
    'attr': 'attrs',
    'dateutil': 'python-dateutil',
    'jwt': 'PyJWT',
    'pymongo': 'pymongo',
    'redis': 'redis',
    'celery': 'celery',
    'aiohttp': 'aiohttp',
    'httpx': 'httpx',
    'pydantic': 'pydantic',
    'fastapi': 'fastapi',
    'uvicorn': 'uvicorn',
    'sqlalchemy': 'sqlalchemy',
}


_UNINDENTED_BODY_RE = re.compile(
    r'(?P<file>\S+?\.py):(?P<body>\d+):\d+:\s*expected an indented block '
    r'after (?:function|class) definition on line (?P<def>\d+)')


__all__ = ['_PY_STDLIB_IMPORTS', '_sibling_py_sources', '_insert_py_imports', '_STDLIB_MODULES', '_PIP_NAME', '_UNINDENTED_BODY_RE']
