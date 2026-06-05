"""Shared environment for the dojo rig — one place for the things every script
used to re-declare (PATH, the archive dir, the LM Studio host, how to call mu).

The shell scripts each exported the same PATH prefix and re-derived ``mu`` and
the session archive. Centralizing them here keeps the three commands honest with
each other and makes the defaults visible in one short file.
"""

import os
import sys
from pathlib import Path


def augment_path() -> None:
    """Prepend the common tool dirs to ``$PATH`` so a subprocess `mu agent` can
    find clang/dotnet/cargo from a bare environment. The canonical list lives in
    mu.toolchain (shared with the product CLI's _extend_path)."""
    from ..toolchain import prepend_tool_paths
    prepend_tool_paths()


def archive_dir() -> Path:
    """Where finalized sessions land (``MU_AGENT_ARCHIVE_DIR``, default
    ``~/.mu/sessions``) — the same default the agent uses."""
    return Path(os.environ.get('MU_AGENT_ARCHIVE_DIR') or Path.home() / '.mu/sessions')


def lmstudio_host() -> str:
    """Base URL for the LM Studio preflight check — the same resolution the
    client uses (env > ~/.mu/config.json > default), not a second copy."""
    from ..client import LMS_HOST
    return LMS_HOST


def mu_cmd() -> list[str]:
    """The argv prefix for invoking mu as a subprocess. Uses the *current*
    interpreter via ``python -m mu`` so the rig and the agent share one venv —
    no PATH guessing, no stale ``./.venv/bin/mu``."""
    return [sys.executable, '-m', 'mu']


def catalog_path() -> str:
    """Path to the problems catalog (``MU_PROBLEMS_CATALOG`` or the repo default
    resolved by ``mu.toolchain``)."""
    return os.environ.get('MU_PROBLEMS_CATALOG', '')


def iso_now() -> str:
    """Local timestamp like ``2026-06-05T16:43:35+02:00`` — the stamp used in the
    digest and the README results block (was ``date -Iseconds`` in the script)."""
    from datetime import datetime
    return datetime.now().astimezone().isoformat(timespec='seconds')
