"""Toolchain availability detection and problem catalog filtering."""

import json
import os
import shutil
from pathlib import Path

# Common tool install locations a non-login shell often omits (dotnet + Homebrew
# on Apple Silicon + Cargo). The canonical list — the CLI and the dojo rig both
# prepend it via prepend_tool_paths() so a subprocess can find clang/dotnet/cargo.
_TOOL_DIRS = (
    '/usr/local/share/dotnet',
    str(Path.home() / '.dotnet'),
    str(Path.home() / '.cargo' / 'bin'),
    '/opt/homebrew/bin',
)


def prepend_tool_paths() -> None:
    """Prepend the common tool dirs to ``$PATH`` (idempotent). Non-existent dirs
    are harmless; the shell just skips them."""
    parts = os.environ.get('PATH', '').split(os.pathsep)
    missing = [d for d in _TOOL_DIRS if d not in parts]
    if missing:
        os.environ['PATH'] = os.pathsep.join(missing + parts)

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


def load_problems_catalog(catalog_path: str | None = None) -> list[dict]:
    """Load the problems catalog from disk."""
    default = Path(__file__).parent.parent.parent / 'problems-catalog.json'
    path = Path(os.environ.get('MU_PROBLEMS_CATALOG', '') or catalog_path or default)
    try:
        return json.loads(path.read_text(encoding='utf-8')).get('problems', [])
    except Exception:
        return []
