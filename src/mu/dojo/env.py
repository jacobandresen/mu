"""Shared environment for the dojo rig — one place for the things every script
used to re-declare (PATH, the archive dir, the LM Studio host, how to call mu).

The shell scripts each exported the same PATH prefix and re-derived ``mu`` and
the session archive. Centralizing them here keeps the three commands honest with
each other and makes the defaults visible in one short file.
"""

import os
import sys
from pathlib import Path

# Tool install locations that are often missing from a non-login shell's PATH
# (dotnet + Homebrew on Apple Silicon + Cargo). Non-existent dirs are harmless.
_TOOL_DIRS = (
    '/usr/local/share/dotnet',
    str(Path.home() / '.dotnet'),
    str(Path.home() / '.cargo/bin'),
    '/opt/homebrew/bin',
)


def augment_path() -> None:
    """Prepend the common tool dirs to ``$PATH`` (idempotent). Mirrors the
    ``export PATH=…`` line the scripts all carried, so a subprocess `mu agent`
    can find clang/dotnet/cargo even when launched from a bare environment."""
    parts = os.environ.get('PATH', '').split(os.pathsep)
    missing = [d for d in _TOOL_DIRS if d not in parts]
    if missing:
        os.environ['PATH'] = os.pathsep.join(missing + parts)


def archive_dir() -> Path:
    """Where finalized sessions land (``MU_AGENT_ARCHIVE_DIR``, default
    ``~/.mu/sessions``) — the same default the agent uses."""
    return Path(os.environ.get('MU_AGENT_ARCHIVE_DIR') or Path.home() / '.mu/sessions')


def lmstudio_host() -> str:
    """Base URL for the LM Studio preflight check (``MU_LMSTUDIO_HOST``)."""
    return os.environ.get('MU_LMSTUDIO_HOST', 'http://localhost:1234')


def mu_cmd() -> list[str]:
    """The argv prefix for invoking mu as a subprocess. Uses the *current*
    interpreter via ``python -m mu`` so the rig and the agent share one venv —
    no PATH guessing, no stale ``./.venv/bin/mu``."""
    return [sys.executable, '-m', 'mu']


def catalog_path() -> str:
    """Path to the problems catalog (``MU_PROBLEMS_CATALOG`` or the repo default
    resolved by ``mu.toolchain``)."""
    return os.environ.get('MU_PROBLEMS_CATALOG', '')
