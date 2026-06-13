"""Shared helpers and constants for the csharp reflexes."""

import re
from pathlib import Path
from mu.reflexes.core import noted


_CS_SIG_RE = re.compile(
    r'^\s*(?:(?:public|private|protected|internal|static|async|override|'
    r'virtual|sealed)\s+)+[\w<>\[\],\s.?]+?\b\w+\s*\([^)]*\)\s*\{?\s*$')


_CS_ATTR_RE = re.compile(r'^\s*\[[\w()", =.]+\]\s*$')


__all__ = ['_CS_SIG_RE', '_CS_ATTR_RE']
