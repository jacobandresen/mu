"""Tool definitions and dispatch for the agent loop.

In AIMA terms this module holds both **actuators** and **percepts**:

* **Actuators** (Write, Edit, Bash) — the only ways mu changes the world.
* **Percepts** (Read + gate stdout captured by ``agent._run_cmd``) — the only
  way mu observes the world. ``_read`` is the primary percept; test/lint gate
  output is the secondary percept fed into the repair loop.

``dispatch`` routes model tool-calls to the correct implementation. Tool
definitions (``WRITE``, ``EDIT``, ``BASH``, ``READ``) are the JSON schemas
passed to the LLM; implementations (``_write``, ``_edit``, ``_bash``, ``_read``)
are the Python functions that execute them.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from mu.degeneration import guard_enabled, is_degenerate, note_refusal

# ── Actuator definitions ──────────────────────────────────────────────────────
# WRITE, EDIT, BASH — the only ways mu changes the world.

WRITE: dict[str, Any] = {
    'type': 'function',
    'function': {
        'name': 'Write',
        'description': 'Write a file with the given content, creating parent directories as needed.',
        'parameters': {
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': 'Absolute or relative file path'},
                'content': {'type': 'string', 'description': 'Complete file content'},
            },
            'required': ['path', 'content'],
        },
    },
}

EDIT: dict[str, Any] = {
    'type': 'function',
    'function': {
        'name': 'Edit',
        'description': 'Replace the first occurrence of old_string with new_string in the file.',
        'parameters': {
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': 'File path'},
                'old_string': {'type': 'string', 'description': 'Exact string to replace'},
                'new_string': {'type': 'string', 'description': 'Replacement string'},
            },
            'required': ['path', 'old_string', 'new_string'],
        },
    },
}

BASH: dict[str, Any] = {
    'type': 'function',
    'function': {
        'name': 'Bash',
        'description': 'Run a shell command and return combined stdout+stderr.',
        'parameters': {
            'type': 'object',
            'properties': {
                'command': {'type': 'string', 'description': 'Shell command to execute'},
            },
            'required': ['command'],
        },
    },
}

# ── Percept definition ────────────────────────────────────────────────────────
# READ — the primary way mu observes the world (file contents as percepts).

READ: dict[str, Any] = {
    'type': 'function',
    'function': {
        'name': 'Read',
        'description': 'Read and return the contents of a file.',
        'parameters': {
            'type': 'object',
            'properties': {
                'path': {'type': 'string', 'description': 'File path to read'},
            },
            'required': ['path'],
        },
    },
}

ALL = [WRITE, EDIT, BASH, READ]
WRITER = [WRITE, EDIT]
REPAIR = [WRITE, EDIT, READ]


def _as_dict(args) -> dict:
    """Tool-call arguments travel as a JSON string (OpenAI schema); parse to dict."""
    if isinstance(args, str):
        try:
            return json.loads(args or '{}')
        except json.JSONDecodeError:
            return {}
    return args or {}


def _coerce_str(val) -> str:
    """Coerce a tool argument to str — models sometimes pass lists instead of strings."""
    if isinstance(val, list):
        return '\n'.join(str(v) for v in val)
    return val if isinstance(val, str) else str(val) if val is not None else ''


def dispatch(name: str, args) -> str:
    """Route a model tool-call by name to the correct implementation.

    Returns the result as a string — tool results are always text so they can
    be appended to the conversation as a ``tool`` role message.
    """
    args = _as_dict(args)
    if name == 'Write':
        return _write(_coerce_str(args.get('path', '')),
                      _coerce_str(args.get('content', '')))
    if name == 'Edit':
        return _edit(_coerce_str(args.get('path', '')),
                     _coerce_str(args.get('old_string', '')),
                     _coerce_str(args.get('new_string', '')))
    if name == 'Bash':
        return _bash(args.get('command', ''))
    if name == 'Read':
        return _read(args.get('path', ''))
    return f"unknown tool: {name}"


def log_call(tc: dict) -> None:
    """Print a one-line summary of a tool call to stdout for the user to follow."""
    tool_call_fn = tc['function']
    args = _as_dict(tool_call_fn['arguments'])
    name = tool_call_fn['name']
    if name in ('Write', 'Edit'):
        print(f"==> [mu-agent] tool: {name}({args.get('path', '')!r})")
    elif name == 'Bash':
        cmd = args.get('command', '')
        print(f"==> [mu-agent] tool: Bash({(cmd[:77] + '...') if len(cmd) > 80 else cmd!r})")
    else:
        print(f"==> [mu-agent] tool: {name}")


# ── Actuator implementations ──────────────────────────────────────────────────

_GENERATED_DIRS = frozenset(['.venv', 'node_modules', '__pycache__', 'target',
                             '.cargo', 'dist', 'build', '.git'])


def _is_generated_path(path: str) -> bool:
    return any(f'/{d}/' in path or path.startswith(f'{d}/') or
               f'/{d}' == path[-len(d) - 1:]
               for d in _GENERATED_DIRS)


# Paths modified by the model through Write/Edit since the last flush. The
# repair loop's reapply hook reads this to run the write-reflex pass on
# exactly the files the last repair turn touched.
_modified: list[str] = []


def _note_modified(path: str) -> None:
    if path not in _modified:
        _modified.append(path)


def flush_modified() -> list[str]:
    """Return and clear the list of model-modified file paths."""
    global _modified
    out, _modified = _modified, []
    return out


def _write(path: str, content: str) -> str:
    if _is_generated_path(path):
        return f"refused: {path} is inside a generated directory — do not modify package manager files"
    if guard_enabled() and is_degenerate(content):
        # The model fell into a repetition loop; writing this would corrupt the
        # file from the first token. Refuse so the writer resamples (docs/challenges/degenerate-repetition.md).
        note_refusal()
        print(f"==> [mu-agent] Degeneration guard: refused corrupt write to {path}")
        return (f"refused: the content for {path} is a repetition loop (degenerate "
                "output), not real code — regenerate it from scratch")
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        _note_modified(path)
        return f"wrote {path} ({len(content)} bytes)"
    except Exception as e:
        return f"error writing file: {e}"


def _edit(path: str, old_str: str, new_str: str) -> str:
    if _is_generated_path(path):
        return f"refused: {path} is inside a generated directory — do not modify package manager files"
    if guard_enabled() and is_degenerate(new_str):
        note_refusal()
        print(f"==> [mu-agent] Degeneration guard: refused corrupt edit to {path}")
        return (f"refused: the replacement text for {path} is a repetition loop "
                "(degenerate output), not real code — regenerate it from scratch")
    try:
        data = Path(path).read_text()
    except Exception as e:
        return f"error reading file: {e}"
    if old_str not in data:
        return f"old_string not found in {path}"
    try:
        Path(path).write_text(data.replace(old_str, new_str, 1))
        _note_modified(path)
        return f"edited {path}"
    except Exception as e:
        return f"error writing file: {e}"


def _bash(command: str) -> str:
    try:
        env = {
            **os.environ,
            "SDL_VIDEODRIVER": "offscreen",
            "SDL_AUDIODRIVER": "dummy",
        }
        result = subprocess.run(['bash', '-c', command], capture_output=True,
                                text=True, timeout=60, env=env)
        out = result.stdout + result.stderr
        return out if out else f"exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return "command timed out"
    except Exception as e:
        return f"error: {e}"


# ── Percept implementation ────────────────────────────────────────────────────

def _read(path: str) -> str:
    try:
        return Path(path).read_text()
    except Exception as e:
        return f"error reading file: {e}"


def extract_code_block(content: str, file_path: str) -> tuple[str, bool]:
    """Extract the first fenced code block from *content* that matches *file_path*'s language.

    Tries language-tagged fences first (e.g. ```python); falls back to a bare
    ``` fence. Returns ``(code, True)`` on success, ``('', False)`` if no
    matching fence was found.
    """
    ext = Path(file_path).suffix.lstrip('.').lower() or Path(file_path).name.lower()
    langs_map = {
        'py': ['python', 'py'], 'go': ['go'], 'c': ['c'], 'h': ['c', 'h'],
        'cpp': ['cpp', 'c++'], 'rs': ['rust', 'rs'], 'cs': ['csharp', 'cs'],
        'js': ['javascript', 'js'], 'ts': ['typescript', 'ts'],
        'sh': ['bash', 'sh', 'shell'], 'toml': ['toml'],
        'yaml': ['yaml', 'yml'], 'yml': ['yaml', 'yml'],
        'json': ['json'], 'makefile': ['makefile', 'make'],
    }
    for lang in langs_map.get(ext, [ext]):
        code, ok = _extract_fence(content, f'```{lang}')
        if ok:
            return code, True
    return _extract_fence(content, '```')


def _extract_fence(content: str, opener: str) -> tuple[str, bool]:
    needle = opener + '\n'
    idx = content.find(needle)
    if idx < 0:
        return '', False
    rest = content[idx + len(needle):]
    end = rest.find('\n```')
    return (rest[:end], True) if end >= 0 else ('', False)
