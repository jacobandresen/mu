"""JavaScript / Node / Jest / Vitest / Vue reflexes: deterministic post-write
fixers for JS sources, package.json, and JS test-runner config. Split out of the
monolithic reflexes module so each language's fixers live together. No logic
changes from the original.
"""

import json
import re
from pathlib import Path


__all__ = [
    'fix_vue_missing_package',
    'fix_vitest_watch_mode',
    'fix_vitest_globals',
    'fix_js_env_data_file',
    'fix_js_missing_requires',
    'fix_js_extra_closing_brace',
    'fix_jest_fs_mock',
    'fix_vue_test_utils_import',
    'fix_jest_no_tests_found',
    'fix_jest_config_js',
    'fix_package_json_bare_jest',
    'fix_package_json_builtin_deps',
    'fix_js_duplicate_require',
]


def fix_vue_missing_package(project_dir: str) -> bool:
    """Add missing Vue ecosystem packages to package.json devDependencies.

    Two cases:
    1. `vue` itself is missing when `@vitejs/plugin-vue` or `@vue/test-utils` is present.
    2. `@vue/test-utils` is missing when a test file imports from it.
    Generic: any project using these packages needs them in devDependencies.
    """
    pkg = Path(project_dir) / 'package.json'
    if not pkg.exists():
        return False
    try:
        data = json.loads(pkg.read_text())
    except Exception:
        return False
    dev = data.get('devDependencies', {})
    deps = data.get('dependencies', {})
    all_pkgs = set(list(dev) + list(deps))
    changed = False

    # Case 1: add `vue` when @vue/* or plugin-vue is present but vue itself is absent
    needs_vue = any(k.startswith('@vue/') or k == '@vitejs/plugin-vue' for k in all_pkgs)
    has_vue = 'vue' in all_pkgs
    if needs_vue and not has_vue:
        dev['vue'] = '^3.4.0'
        changed = True
        print(f"==> [mu-agent] Reflex: added missing vue package to {pkg}")

    # Case 2: add `@vue/test-utils` when a test file imports it but it's not in package.json
    has_test_utils = '@vue/test-utils' in all_pkgs
    if not has_test_utils:
        test_files = list(Path(project_dir).rglob('*.test.ts')) + \
                     list(Path(project_dir).rglob('*.test.js')) + \
                     list(Path(project_dir).rglob('*.spec.ts'))
        for tf in test_files:
            if 'node_modules' in str(tf):
                continue
            try:
                if '@vue/test-utils' in tf.read_text():
                    dev['@vue/test-utils'] = '^2.4.0'
                    changed = True
                    print(f"==> [mu-agent] Reflex: added missing @vue/test-utils to {pkg}")
                    break
            except OSError:
                pass

    if not changed:
        return False
    data['devDependencies'] = dev
    pkg.write_text(json.dumps(data, indent=2) + '\n')
    return True

def fix_vitest_watch_mode(project_dir: str) -> bool:
    """Replace bare `vitest` with `vitest run` in package.json test scripts.

    `vitest` without arguments starts in watch mode and waits for file changes
    indefinitely, causing the test command to hang. `vitest run` executes once
    and exits with a pass/fail code. This fires whenever package.json uses the
    bare `vitest` command as the test script.
    """
    pkg = Path(project_dir) / 'package.json'
    if not pkg.exists():
        return False
    try:
        text = pkg.read_text()
        data = json.loads(text)
    except Exception:
        return False
    scripts = data.get('scripts', {})
    changed = False
    for key in list(scripts):
        val = scripts[key]
        if isinstance(val, str) and re.search(r'\bvitest\b(?!\s+run\b)', val):
            scripts[key] = re.sub(r'\bvitest\b(?!\s+run\b)', 'vitest run', val)
            changed = True
    if not changed:
        return False
    data['scripts'] = scripts
    pkg.write_text(json.dumps(data, indent=2) + '\n')
    print(f"==> [mu-agent] Reflex: changed vitest to vitest run in {pkg}")
    return True

def fix_vitest_globals(project_dir: str, test_output: str) -> bool:
    """Enable Vitest globals when test output reports 'test is not defined'.

    Vitest does not expose test/expect/describe as globals by default. Without
    `globals: true` in vite.config.ts, calling test(...) raises ReferenceError.
    This reflex adds globals: true to the test config block. General: any Vitest
    project that uses bare test() calls needs globals enabled.
    """
    if 'is not defined' not in test_output and 'ReferenceError' not in test_output:
        return False
    if not any(name in test_output for name in ('test', 'expect', 'describe', 'beforeEach', 'it')):
        return False
    config_path = Path(project_dir) / 'vite.config.ts'
    if not config_path.exists():
        config_path = Path(project_dir) / 'vite.config.js'
    if not config_path.exists():
        return False
    try:
        text = config_path.read_text()
    except OSError:
        return False
    if 'globals: true' in text or "globals:true" in text:
        return False
    # Add globals: true inside the test: { ... } block
    new_text = re.sub(
        r'(test\s*:\s*\{)',
        r'\1\n    globals: true,',
        text,
        count=1,
    )
    if new_text == text:
        # No test block found — append a minimal one
        if 'test:' not in text:
            new_text = re.sub(
                r'(export default defineConfig\(\{)',
                r'\1\n  test: { environment: "jsdom", globals: true },',
                text,
                count=1,
            )
    if new_text == text:
        return False
    config_path.write_text(new_text)
    print(f"==> [mu-agent] Reflex: added Vitest globals:true to {config_path}")
    return True

def fix_js_env_data_file(file_path: str) -> bool:
    """Convert hardcoded JSON file paths to env-var getter functions for test isolation.

    Two patterns handled:
    A. Module-level `const DATA_FILE = process.env.X || 'default'` — captured at
       load time so Jest beforeEach changes to process.env.X have no effect.
    B. Hardcoded `'./data.json'` or `'todos.json'` etc. inline in function bodies
       with no env-var indirection at all — tests can't override the path.

    Both are converted to `function getDataFile() { return process.env.TODO_FILE || 'data.json'; }`
    with call-sites rewritten to `getDataFile()`, enabling per-test temp-file isolation.
    General: applies to any CommonJS source file used by a test suite.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.js', '.jsx', '.mjs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Skip test files
    stem = Path(file_path).stem.lower()
    if stem.startswith('test_') or stem.endswith('_test') or '.test' in stem or '.spec' in stem:
        return False
    # Skip if already has a getDataFile() or similar getter
    if 'getDataFile' in text or 'getData_file' in text:
        return False

    changed = False
    new_text = text

    # Pattern A: module-level const with env var
    m = re.search(
        r'^(const\s+(\w+)\s*=\s*process\.env\.(\w+)\s*\|\|\s*[\'"][^\'"]+[\'"])\s*;',
        new_text, re.MULTILINE,
    )
    if m:
        const_line, var_name = m.group(1) + ';', m.group(2)
        full_expr = m.group(1).split('=', 1)[1].strip()
        line_start = new_text.rfind('\n', 0, m.start()) + 1
        if not new_text[line_start:m.start()].strip():  # not indented
            parts = var_name.split('_')
            camel = parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])
            getter_name = 'get' + camel[0].upper() + camel[1:]
            getter_fn = f'function {getter_name}() {{ return {full_expr}; }}'
            new_text = new_text.replace(const_line, getter_fn, 1)
            new_text = re.sub(rf'\b{re.escape(var_name)}\b', f'{getter_name}()', new_text)
            changed = True
            print(f"==> [mu-agent] Reflex: converted {var_name} to {getter_name}() in {file_path}")

    # Pattern B: hardcoded .json path string used in ≥2 function bodies with no env-var override
    if not changed:
        json_paths = re.findall(r'''['"](\.?/?[\w./]*\.json)['"]\s*[,)]''', new_text)
        # Only fire when the same literal path appears multiple times (used in multiple functions)
        from collections import Counter
        counts = Counter(json_paths)
        target = next((p for p, c in counts.items() if c >= 2), None)
        if target:
            env_var = 'TODO_FILE' if 'todo' in target.lower() else 'DATA_FILE'
            getter_fn = f"function getDataFile() {{ return process.env.{env_var} || '{target}'; }}"
            # Replace occurrences in the original text FIRST, then insert getter
            replaced = re.sub(
                rf'''(['"]){re.escape(target)}\1''',
                'getDataFile()',
                new_text,
            )
            replaced = replaced.replace("'getDataFile()'", 'getDataFile()')
            replaced = replaced.replace('"getDataFile()"', 'getDataFile()')
            # Insert getter after the last require() line
            insert_after = max((m.end() for m in re.finditer(r'^.*require\s*\(.*\)\s*;?$', replaced, re.MULTILINE)), default=0)
            insert_pos = replaced.find('\n', insert_after) + 1 if insert_after else 0
            new_text = replaced[:insert_pos] + getter_fn + '\n' + replaced[insert_pos:]
            changed = True
            print(f"==> [mu-agent] Reflex: converted hardcoded '{target}' to getDataFile() in {file_path}")

    if not changed or new_text == text:
        return False
    Path(file_path).write_text(new_text)
    return True

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

def fix_js_missing_requires(file_path: str) -> bool:
    """Add missing Node.js built-in require() calls to CommonJS JS files.

    Models often use `path.join()`, `os.tmpdir()`, `fs.readFileSync()` etc.
    without the corresponding `require()` at the top of the file, causing
    `ReferenceError: path is not defined` at runtime. Detects usage via
    `module.method` patterns and adds the missing require statements.
    General: applies to any CommonJS Node.js file.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.js', '.jsx', '.mjs'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Skip ESM files (import/export syntax)
    if re.search(r'^\s*(?:import|export)\s', text, re.MULTILINE):
        return False
    to_add = []
    for mod, stmt in _JS_NODE_BUILTINS.items():
        if re.search(rf'require\([\'\"]{re.escape(mod)}[\'\"]\)', text):
            continue  # already required
        if _JS_MODULE_USE_RE[mod].search(text):
            to_add.append(stmt)
    if not to_add:
        return False
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('const ') and 'require(' in stripped:
            insert_at = i + 1
        elif stripped and not stripped.startswith('//') and not stripped.startswith('/*') \
                and insert_at > 0:
            break
    for stmt in reversed(to_add):
        lines.insert(insert_at, stmt)
    Path(file_path).write_text('\n'.join(lines) + '\n')
    print(f"==> [mu-agent] Reflex: added {len(to_add)} missing Node.js require(s) to {file_path}")
    return True


# `const NAME = require(...)` / `import NAME = require(...)`, captured by NAME.
_JS_REQUIRE_DECL_RE = re.compile(
    r'^\s*(?:const|let|var)\s+(?P<name>\w+)\s*=\s*require\(')


def fix_js_duplicate_require(file_path: str) -> bool:
    """Remove a duplicate top-level ``const X = require(...)`` declaration.

    A weak model sometimes emits the same require twice (observed:
    ``const fs = require('fs')`` on two lines), which is a hard
    ``SyntaxError: Identifier 'fs' has already been declared`` — Jest/Babel can't
    even parse the file. Keep the first declaration of each name and drop later
    ones. General: re-declaring the same identifier with ``const`` is always
    invalid JS, in any file — the JS analogue of fix_rust_duplicate_use.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.js', '.jsx', '.mjs', '.ts', '.tsx'):
        return False
    try:
        lines = Path(file_path).read_text().splitlines()
    except OSError:
        return False
    seen: set[str] = set()
    out, removed = [], 0
    for line in lines:
        m = _JS_REQUIRE_DECL_RE.match(line)
        if m:
            name = m.group('name')
            if name in seen:
                removed += 1
                continue  # drop the redeclaration
            seen.add(name)
        out.append(line)
    if not removed:
        return False
    Path(file_path).write_text('\n'.join(out) + '\n')
    print(f"==> [mu-agent] Reflex: removed {removed} duplicate require declaration(s) from {file_path}")
    return True

def fix_js_extra_closing_brace(file_path: str, test_output: str = '') -> bool:
    """Fix unbalanced braces in JS/TS files when the parser reports a mismatch.

    esbuild / Vitest reports `Unexpected "}"` when a .ts/.js file has more `}`
    than `{`, or `Expected "}" but found ")"` when the reverse is true. This
    reflex counts braces (ignoring strings, template literals, and comments)
    and either removes trailing `}` lines (extra braces) or appends missing
    `}` characters (missing braces). General: applies to any JS/TS file.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.ts', '.tsx', '.js', '.jsx'):
        return False
    if test_output and not any(s in test_output for s in
                               ('Unexpected', 'SyntaxError', 'Expected "}"', 'Transform failed')):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False

    # Count braces AND parens outside strings/comments
    depth = 0  # { vs }
    paren_depth = 0  # ( vs )
    i = 0
    while i < len(text):
        c = text[i]
        # Skip single-line comment
        if c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        # Skip block comment
        if c == '/' and i + 1 < len(text) and text[i + 1] == '*':
            i += 2
            while i + 1 < len(text) and not (text[i] == '*' and text[i + 1] == '/'):
                i += 1
            i += 2
            continue
        # Skip single-quoted string
        if c == "'":
            i += 1
            while i < len(text) and text[i] != "'":
                if text[i] == '\\':
                    i += 1
                i += 1
        # Skip double-quoted string
        elif c == '"':
            i += 1
            while i < len(text) and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
        # Skip template literal (backtick) — simplified, ignores ${...}
        elif c == '`':
            i += 1
            while i < len(text) and text[i] != '`':
                if text[i] == '\\':
                    i += 1
                i += 1
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        elif c == '(':
            paren_depth += 1
        elif c == ')':
            paren_depth -= 1
        i += 1

    if depth == 0 and paren_depth == 0:
        return False  # already balanced

    # Prefer fixing paren imbalance first (simpler — just remove trailing `)`)
    if paren_depth < 0 and depth == 0:
        # Too many `)`: remove trailing `)` or `))` from the last line
        lines = text.rstrip().splitlines()
        new_lines = list(lines)
        removed = 0
        for idx in range(len(lines) - 1, -1, -1):
            if removed >= abs(paren_depth):
                break
            stripped = new_lines[idx].rstrip()
            if stripped.endswith(')') or stripped.endswith('))'):
                count = min(abs(paren_depth) - removed, stripped.count(')') - stripped.count('('))
                if count > 0:
                    new_lines[idx] = stripped[:-count]
                    removed += count
        if removed:
            Path(file_path).write_text('\n'.join(new_lines) + '\n')
            print(f"==> [mu-agent] Reflex: removed {removed} extra ')' from {file_path}")
            return True

    if depth < 0:
        # Too many `}`: remove or trim trailing `}` lines
        lines = text.rstrip().splitlines()
        removed = 0
        new_lines = list(lines)
        for idx in range(len(lines) - 1, -1, -1):
            if removed >= abs(depth):
                break
            stripped = new_lines[idx].strip()
            # Handle single `}` or `};` lines
            if stripped in ('}', '};'):
                del new_lines[idx]
                removed += 1
            # Handle `}}` or `}};` — remove one `}` at a time from the right
            elif re.match(r'^[}]+;?$', stripped) and len(stripped.rstrip(';')) > 1:
                extra = len(stripped.rstrip(';')) - 1
                to_remove = min(extra, abs(depth) - removed)
                new_stripped = stripped[to_remove:]
                new_lines[idx] = new_stripped
                removed += to_remove
        if not removed:
            return False
        Path(file_path).write_text('\n'.join(new_lines) + '\n')
        print(f"==> [mu-agent] Reflex: removed {removed} extra closing brace(s) from {file_path}")
        return True
    else:
        # Too many `{`: append `depth` closing braces
        Path(file_path).write_text(text.rstrip() + '\n' + '}\n' * depth)
        print(f"==> [mu-agent] Reflex: added {depth} missing closing brace(s) to {file_path}")
        return True

def fix_jest_fs_mock(file_path: str) -> bool:
    """Complete a jest.mock('fs', ...) factory that is missing jest.fn() entries.

    When a test does `jest.mock('fs', () => ({ writeFileSync: jest.fn() }))` but
    later calls `fs.readFileSync.mockReturnValue(...)`, the test fails because
    readFileSync wasn't mocked. This reflex detects incomplete fs mock factories
    and ensures all accessed fs methods are included as jest.fn().
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.js', '.jsx', '.mjs', '.ts', '.tsx'):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Only process files with jest.mock('fs', ...) factory form
    if "jest.mock('fs'" not in text and 'jest.mock("fs"' not in text:
        return False
    # Find which fs methods the test calls .mockReturnValue / .mockResolvedValue / .mockImplementation on
    called_mocks = set(re.findall(r'\bfs\.(\w+)\.mock', text))
    if not called_mocks:
        return False
    # Find the mock factory body and check what's already there
    m = re.search(r"jest\.mock\(['\"]fs['\"],\s*\(\)\s*=>\s*\{(.*?)\}\s*\)",
                  text, re.DOTALL)
    if not m:
        return False
    factory_body = m.group(1)
    missing = [fn for fn in called_mocks if fn not in factory_body]
    if not missing:
        return False
    # Add missing entries before the closing brace of the factory
    additions = ',\n    '.join(f'{fn}: jest.fn()' for fn in sorted(missing))
    # Insert before the last non-whitespace content in the factory body
    new_factory = factory_body.rstrip()
    if new_factory.endswith(','):
        new_factory += f'\n    {additions}'
    else:
        new_factory += f',\n    {additions}'
    new_text = text[:m.start(1)] + new_factory + text[m.end(1):]
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: added missing jest.fn() to fs mock in {file_path}")
    return True

def fix_vue_test_utils_import(file_path: str) -> bool:
    """Replace wrong Vue test utility import sources with @vue/test-utils.

    Models occasionally import `mount` or `shallowMount` from non-existent
    packages like `vue-router-dom`, `@testing-library/vue`, or bare `vue`.
    In Vue 3 + Vitest projects the correct import is always `@vue/test-utils`.
    Fires on any TypeScript/JavaScript test file that mounts Vue components.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in ('.ts', '.tsx', '.js', '.jsx'):
        return False
    stem = Path(file_path).stem.lower()
    if not (stem.endswith('.test') or stem.endswith('.spec') or
            'test' in stem or 'spec' in stem):
        return False
    try:
        text = Path(file_path).read_text()
    except OSError:
        return False
    # Only fix if the file imports mount/shallowMount/flushPromises from a wrong source
    wrong_sources = (
        r"'vue-router-dom'",
        r'"vue-router-dom"',
        r"'@testing-library/vue'",
        r'"@testing-library/vue"',
        r"from\s+['\"]vue['\"]",   # bare `from 'vue'` when used for mount
    )
    # Check that mount or shallowMount is being imported
    if not re.search(r'\b(mount|shallowMount|flushPromises)\b', text):
        return False
    new_text = text
    for pattern in wrong_sources[:4]:  # literal string replacements
        for fn in ('mount', 'shallowMount', 'flushPromises'):
            new_text = re.sub(
                rf"""(import\s*\{{[^}}]*\b{fn}\b[^}}]*\}})\s*from\s+{pattern}""",
                r"\1 from '@vue/test-utils'",
                new_text,
            )
    if new_text == text:
        return False
    Path(file_path).write_text(new_text)
    print(f"==> [mu-agent] Reflex: fixed Vue test-utils import in {file_path}")
    return True

def fix_jest_no_tests_found(test_output: str, project_dir: str) -> bool:
    """Add testRegex to package.json when Jest reports 'No tests found'.

    Jest's default testMatch pattern requires `.test.js` / `.spec.js` suffixes.
    When a project uses `_test.js` (Python-style) or another convention, Jest
    exits 1 with 'No tests found'. This reflex broadens the testRegex in
    package.json to match `_test.js` / `_spec.js` in addition to the defaults.
    General: driven entirely by Jest's error message, not any specific project.
    """
    if 'No tests found' not in test_output:
        return False
    pkg_path = Path(project_dir) / 'package.json'
    if not pkg_path.exists():
        return False
    try:
        import json as _json
        data = _json.loads(pkg_path.read_text())
    except Exception:
        return False
    all_deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
    jest_in_scripts = any('jest' in str(v) for v in data.get('scripts', {}).values())
    if 'jest' not in all_deps and not jest_in_scripts:
        return False
    # Already has testRegex or testMatch configured — don't override.
    jest_cfg = data.get('jest', {})
    if jest_cfg.get('testRegex') or jest_cfg.get('testMatch'):
        return False
    # Find actual test files in the project dir to figure out their naming.
    # Match both suffix-style (todo.test.js) and prefix-style (test_todo.js).
    existing = [
        p.name for p in Path(project_dir).iterdir()
        if p.is_file() and (
            re.search(r'[._-](test|spec)\.[jt]sx?$', p.name)
            or (re.match(r'^test_', p.name) and p.suffix.lower() in ('.js', '.jsx', '.mjs', '.ts', '.tsx'))
        )
    ]
    if not existing:
        return False
    # Match suffix-style (.test.js, _test.js) and prefix-style (test_*.js).
    data.setdefault('jest', {})['testRegex'] = r'(test_.*|.*[._-](test|spec))\.[jt]sx?$'
    pkg_path.write_text(_json.dumps(data, indent=2) + '\n')
    print(f"==> [mu-agent] Reflex: added Jest testRegex to {pkg_path} (No tests found)")
    return True

def fix_jest_config_js(project_dir: str) -> bool:
    """Fix jest.config.js files that use JSON syntax instead of CommonJS module syntax.

    Models sometimes write jest.config.js with JSON-style key-value pairs
    (quoted keys, no `module.exports`) which causes `SyntaxError: Unexpected token ':'`.
    If package.json already has a `jest` config section, just delete jest.config.js
    to remove the conflict. Otherwise, wrap the content in `module.exports = {...}`.
    General: any jest.config.js that uses JSON syntax will fail at load time.
    """
    cfg_path = Path(project_dir) / 'jest.config.js'
    if not cfg_path.exists():
        return False
    try:
        text = cfg_path.read_text()
    except OSError:
        return False
    # Detect JSON-style syntax: starts with `{` and uses `"key":` pairs (no module.exports)
    stripped = text.strip()
    if 'module.exports' in text or not stripped.startswith('{'):
        return False
    # If package.json already has a jest config, delete the conflicting file
    pkg_path = Path(project_dir) / 'package.json'
    if pkg_path.exists():
        try:
            import json as _json
            data = _json.loads(pkg_path.read_text())
            if data.get('jest'):
                cfg_path.unlink()
                print("==> [mu-agent] Reflex: removed conflicting jest.config.js (config in package.json)")
                return True
        except Exception:
            pass
    # Otherwise convert JSON-style to CommonJS
    cfg_path.write_text(f'module.exports = {stripped};\n')
    print("==> [mu-agent] Reflex: converted jest.config.js from JSON to CommonJS format")
    return True

def fix_package_json_bare_jest(project_dir: str) -> bool:
    """Replace bare `jest` in package.json scripts.test with `npx jest --forceExit`.
    Also sets testRegex to match both `.test.js` and `_test.js` naming conventions.

    When a model writes `"test": "jest"` in package.json scripts, running
    `npm test` invokes `jest` directly which is not on the shell PATH. The
    locally-installed binary lives in `node_modules/.bin/` and must be reached
    via `npx`. Generic: applies to any project with jest as a dependency.

    Also adds testRegex proactively to handle `_test.js` naming (Python-style).
    Doing this at write time rather than reactively prevents the repair model
    from reverting the testRegex added by fix_jest_no_tests_found.
    """
    pkg_path = Path(project_dir) / 'package.json'
    if not pkg_path.exists():
        return False
    try:
        import json as _json
        data = _json.loads(pkg_path.read_text())
    except Exception:
        return False
    all_deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
    scripts = data.get('scripts', {})
    jest_in_scripts = any('jest' in str(v) for v in scripts.values())
    if 'jest' not in all_deps and not jest_in_scripts:
        return False
    changed = False
    test_script = scripts.get('test', '')
    # Replace bare `jest` (with or without flags, but not already prefixed with npx)
    if test_script and 'npx' not in test_script and re.match(r'^jest\b', test_script):
        new_script = re.sub(r'^jest\b', 'npx jest', test_script)
        if '--forceExit' not in new_script:
            new_script = new_script.rstrip() + ' --forceExit'
        data.setdefault('scripts', {})['test'] = new_script
        print(f"==> [mu-agent] Reflex: replaced bare jest with npx jest in {pkg_path}")
        changed = True
    # Also proactively add testRegex to handle _test.js and test_*.js naming conventions
    jest_cfg = data.get('jest', {})
    correct_regex = r'(test_.*|.*[._-](test|spec))\.[jt]sx?$'
    if not jest_cfg.get('testRegex') or jest_cfg.get('testRegex') == '':
        data.setdefault('jest', {})['testRegex'] = correct_regex
        print(f"==> [mu-agent] Reflex: added testRegex to jest config in {pkg_path}")
        changed = True
    if not changed:
        return False
    pkg_path.write_text(_json.dumps(data, indent=2) + '\n')
    return True


def fix_package_json_builtin_deps(project_dir: str) -> bool:
    """Remove Node.js core modules from package.json dependencies/devDependencies.

    Node builtins (``fs``, ``path``, ``http`` …) ship with the runtime and are not
    on the npm registry, so listing one as a dependency makes ``npm install`` fail
    with ETARGET / "No matching version found" (observed: the model invents
    ``"fs": "^14.17.0"``). General: a builtin is never a valid npm dependency in
    any Node project — the JS analogue of stripping stdlib names from
    requirements.txt or invalid versions from Cargo.toml.
    """
    pkg_path = Path(project_dir) / 'package.json'
    if not pkg_path.exists():
        return False
    try:
        import json as _json
        data = _json.loads(pkg_path.read_text())
    except Exception:
        return False
    removed: list[str] = []
    for section in ('dependencies', 'devDependencies'):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for name in list(deps):
            # Match both bare ("fs") and node:-prefixed ("node:fs") spellings.
            core = name[5:] if name.startswith('node:') else name
            if core in _NODE_CORE_MODULES:
                del deps[name]
                removed.append(name)
        if not deps:
            data.pop(section, None)
    if not removed:
        return False
    pkg_path.write_text(_json.dumps(data, indent=2) + '\n')
    print(f"==> [mu-agent] Reflex: removed Node builtin(s) from {pkg_path}: {removed}")
    return True
