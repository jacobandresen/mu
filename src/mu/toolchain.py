"""Toolchain availability detection and problem catalog filtering."""

import json
import os
import shutil
from pathlib import Path

# Toolchain name → binaries that must all be present on PATH
TOOLCHAINS: dict[str, dict] = {
    'clang':   {'bins': ['clang'],          'hint': 'brew install llvm / apt install clang'},
    'go':      {'bins': ['go'],             'hint': 'brew install go / apt install golang'},
    'cargo':   {'bins': ['cargo', 'rustc'], 'hint': 'brew install rustup && rustup toolchain install stable'},
    'dotnet':  {'bins': ['dotnet'],         'hint': 'brew install dotnet / apt install dotnet-sdk-8.0'},
    'python3': {'bins': ['python3'],        'hint': 'pre-installed on macOS; apt install python3'},
    'node':    {'bins': ['node', 'npm'],    'hint': 'brew install node / apt install nodejs npm'},
    'sdl2':    {'bins': ['sdl2-config'],    'hint': 'brew install SDL2 / apt install libsdl2-dev'},
}


def available() -> set[str]:
    """Return toolchain names where every required binary is on PATH."""
    return {name for name, spec in TOOLCHAINS.items()
            if all(shutil.which(b) for b in spec['bins'])}


def status() -> list[dict]:
    """Return one entry per toolchain with availability info and install hint."""
    rows = []
    for name, spec in TOOLCHAINS.items():
        missing_bin = next((b for b in spec['bins'] if not shutil.which(b)), None)
        rows.append({
            'name':        name,
            'available':   missing_bin is None,
            'path':        shutil.which(spec['bins'][0]) if missing_bin is None else None,
            'missing_bin': missing_bin,
            'hint':        spec['hint'],
        })
    return rows


# File extension → toolchain
_EXT_TOOL: dict[str, str] = {
    '.c':   'clang',
    '.cpp': 'clang',
    '.go':  'go',
    '.rs':  'cargo',
    '.cs':  'dotnet',
    '.py':  'python3',
    '.js':  'node',
    '.ts':  'node',
}

# Test-command substring → toolchain
_CMD_TOOL: list[tuple[str, str]] = [
    ('cargo',  'cargo'),
    ('dotnet', 'dotnet'),
    ('go ',    'go'),
    ('clang',  'clang'),
    ('gcc',    'clang'),
    ('pytest', 'python3'),
    ('python', 'python3'),
    ('node',   'node'),
    ('npm',    'node'),
    ('sdl2',   'sdl2'),
]


def required_by_plan(file_paths: list[str], test_cmd: str) -> set[str]:
    """Infer toolchain names needed to build and test a plan."""
    needed: set[str] = set()
    for fp in file_paths:
        tool = _EXT_TOOL.get(Path(fp).suffix.lower())
        if tool:
            needed.add(tool)
    cmd = (test_cmd or '').lower()
    for fragment, tool in _CMD_TOOL:
        if fragment in cmd:
            needed.add(tool)
    return needed


def missing_for_plan(file_paths: list[str], test_cmd: str) -> set[str]:
    """Return toolchains the plan needs but are not installed."""
    return required_by_plan(file_paths, test_cmd) - available()


def load_problems_catalog(catalog_path: str | None = None) -> list[dict]:
    """Load the problems catalog from disk."""
    default = Path(__file__).parent.parent.parent / 'problems-catalog.json'
    path = Path(os.environ.get('MU_PROBLEMS_CATALOG', '') or catalog_path or default)
    try:
        return json.loads(path.read_text(encoding='utf-8')).get('problems', [])
    except Exception:
        return []


def available_problems(catalog_path: str | None = None) -> list[dict]:
    """Return problems whose required toolchains are all installed."""
    avail = available()
    return [
        p for p in load_problems_catalog(catalog_path)
        if set(p.get('toolchains', [])) <= avail
    ]
