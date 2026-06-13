"""Shared helpers and constants for the javascript reflexes."""

import json
import re
from pathlib import Path
from mu.reflexes.core import _fix_duplicate_decls, fix_literal_newlines, noted


_JS_NODE_BUILTINS: dict[str, str] = {
    'path': "const path = require('path');",
    'os': "const os = require('os');",
    'fs': "const fs = require('fs');",
    'crypto': "const crypto = require('crypto');",
    'url': "const url = require('url');",
    'http': "const http = require('http');",
    'https': "const https = require('https');",
    'util': "const util = require('util');",
    'assert': "const assert = require('assert');",
    'events': "const events = require('events');",
    'stream': "const stream = require('stream');",
    'child_process': "const child_process = require('child_process');",
}


_JS_MODULE_USE_RE = {
    mod: re.compile(rf'\b{re.escape(mod)}\s*\.')
    for mod in _JS_NODE_BUILTINS
}


# Node.js core modules. These ship with the runtime and are NOT on the npm
# registry, so listing one in package.json dependencies makes `npm install` fail
# with ETARGET/"No matching version found". The fuller set (beyond the require-
# insertion list above) is needed because the model invents versions for any of
# them (observed: `"fs": "^14.17.0"`).
_NODE_CORE_MODULES = frozenset({
    'assert', 'async_hooks', 'buffer', 'child_process', 'cluster', 'console',
    'constants', 'crypto', 'dgram', 'dns', 'domain', 'events', 'fs', 'http',
    'http2', 'https', 'inspector', 'module', 'net', 'os', 'path', 'perf_hooks',
    'process', 'punycode', 'querystring', 'readline', 'repl', 'stream',
    'string_decoder', 'sys', 'timers', 'tls', 'tty', 'url', 'util', 'v8', 'vm',
    'worker_threads', 'zlib',
})


# `const NAME = require(...)` / `import NAME = require(...)`, captured by NAME.
_JS_REQUIRE_DECL_RE = re.compile(
    r'^\s*(?:const|let|var)\s+(?P<name>\w+)\s*=\s*require\(')


_JS_EXTS = frozenset(('.js', '.jsx', '.mjs', '.ts', '.tsx'))


__all__ = ['_JS_NODE_BUILTINS', '_JS_MODULE_USE_RE', '_NODE_CORE_MODULES', '_JS_REQUIRE_DECL_RE', '_JS_EXTS']
