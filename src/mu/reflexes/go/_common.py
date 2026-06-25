"""Shared helpers and constants for the go reflexes."""

import re
import shutil
import subprocess
from pathlib import Path


_GO_UNUSED_IMPORT_RE = re.compile(r'^(\S+):\d+:\d+: "([^"]+)" imported and not used')


# `go vet ./...` reports paths module-relative WITHOUT a `./` prefix in multi-package
# projects (e.g. `vet: backend/tests/ping_test.go:14:7: undefined: httptest`), while a
# single-package `go build` may emit `./file.go:…`. The `./` must be optional or the
# reflex silently no-ops on every staged Go project (the common p5-gin layout).
_UNDEF_RE = re.compile(r'(?:vet: )?(?:\./)?([\w/.-]+\.go):\d+:\d+: undefined: (\w+)')


# stdlib packages whose package name doesn't equal the last path segment, or
# that models commonly omit. Keyed by the identifier used in source.
_STDLIB_IMPORTS: dict[str, str] = {
    'httptest':  'net/http/httptest',
    'http':      'net/http',
    'url':       'net/url',
    'json':      'encoding/json',
    'rand':      'math/rand',
    'filepath':  'path/filepath',
    'ioutil':    'io/ioutil',
    'bufio':     'bufio',
    'context':   'context',
    'errors':    'errors',
    'fmt':       'fmt',
    'io':        'io',
    'log':       'log',
    'math':      'math',
    'os':        'os',
    'sort':      'sort',
    'strconv':   'strconv',
    'strings':   'strings',
    'sync':      'sync',
    'time':      'time',
}


__all__ = ['_GO_UNUSED_IMPORT_RE', '_UNDEF_RE', '_STDLIB_IMPORTS']
