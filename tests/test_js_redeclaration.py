"""Tests for fix_js_same_scope_redeclaration, fix_js_dot_bracket_access, and
the diagnose weak-hint demotion that surfaced them.

The fixtures mirror real p8-node-todo failures from ~/.mu/sessions: qwen
re-declares `const todos = readTodos();` mid-test (Babel: "Identifier 'todos'
has already been declared") and emits `).[0].id` member access (Babel:
"Unexpected token"). Both arrived mislabeled as "Jest: ESM/CJS parse error"
because Jest's banner line preceded the SyntaxError detail.
"""

from pathlib import Path

from mu.diagnose import distill_test_errors
from mu.reflexes.javascript import (fix_js_dot_bracket_access,
                                    fix_js_same_scope_redeclaration)

_ERR = "SyntaxError: /tmp/x/todo.test.js: Identifier 'todos' has already been declared. (38:10)"


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / 'todo.test.js'
    p.write_text(body)
    return p


def test_redeclaration_same_block_becomes_assignment(tmp_path):
    # The observed shape: re-read state mid-test with a second `const todos`.
    p = _write(tmp_path, """\
test('deletes a todo', () => {
  const todos = readTodos();
  writeTodos([{ task: 'buy milk', id: 1 }]);
  const todos = readTodos();
  expect(todos.length).toBe(1);
});
""")
    assert fix_js_same_scope_redeclaration(str(p), _ERR)
    out = p.read_text()
    assert 'let todos = readTodos();' in out          # first decl promoted
    assert out.count('const todos') == 0
    assert '\n  todos = readTodos();\n' in out        # second decl now assigns


def test_redeclaration_let_then_const(tmp_path):
    p = _write(tmp_path, """\
test('lists todos', () => {
  let todos = JSON.parse(fs.readFileSync('todos.json', 'utf8')) || [];
  const todos = todoManager.list();
  expect(todos).toEqual([]);
});
""")
    assert fix_js_same_scope_redeclaration(str(p), _ERR)
    out = p.read_text()
    assert out.count('const todos') == 0
    assert 'let todos = JSON.parse' in out
    assert '  todos = todoManager.list();' in out


def test_redeclaration_degenerate_repetition_mixed_indent(tmp_path):
    # Degenerate repetition at column 0 is still the same brace scope.
    p = _write(tmp_path, """\
test('x', () => {
  const todos = readTodos();
  writeTodos([{ task: 'buy milk', id: Date.now() }]);
  const todos = readTodos();
const todos = readTodos();
const todos = readTodos();
  expect(todos).toEqual([]);
});
""")
    assert fix_js_same_scope_redeclaration(str(p), _ERR)
    out = p.read_text()
    assert out.count('const todos') == 0
    assert out.count('let todos') == 1


def test_shadowing_in_inner_block_untouched(tmp_path):
    # Legal shadowing: const in a nested block is a different scope.
    body = """\
const todos = [];
test('x', () => {
  const todos = readTodos();
  expect(todos).toEqual([]);
});
"""
    p = _write(tmp_path, body)
    assert not fix_js_same_scope_redeclaration(str(p), _ERR)
    assert p.read_text() == body


def test_sibling_test_blocks_untouched(tmp_path):
    body = """\
test('a', () => {
  const todos = readTodos();
});
test('b', () => {
  const todos = readTodos();
});
"""
    p = _write(tmp_path, body)
    assert not fix_js_same_scope_redeclaration(str(p), _ERR)
    assert p.read_text() == body


def test_var_var_redeclaration_is_legal_and_untouched(tmp_path):
    body = "var x = 1;\nvar x = 2;\n"
    p = _write(tmp_path, body)
    assert not fix_js_same_scope_redeclaration(str(p), _ERR)
    assert p.read_text() == body


def test_braces_inside_strings_do_not_open_scopes(tmp_path):
    # The '{' in the string literal must not fork a scope, or the conflict
    # at the same real depth would be missed.
    p = _write(tmp_path, """\
test('x', () => {
  const s = 'a { b';
  const todos = readTodos();
  const todos = readTodos();
});
""")
    assert fix_js_same_scope_redeclaration(str(p), _ERR)
    assert p.read_text().count('const todos') == 0


def test_redeclaration_gated_on_error_output(tmp_path):
    p = _write(tmp_path, "const a = 1;\nconst a = 2;\n")
    assert not fix_js_same_scope_redeclaration(str(p), 'tests failed: wrong value')


def test_dot_bracket_access_removed(tmp_path):
    # Observed: `...mockResolvedValueOnce([...])).[0].id`
    p = _write(tmp_path, "const id = JSON.parse(todos).[0].id;\n")
    assert fix_js_dot_bracket_access(str(p), 'SyntaxError: Unexpected token (40:124)')
    assert p.read_text() == "const id = JSON.parse(todos)[0].id;\n"


def test_dot_bracket_leaves_optional_chaining_and_spread(tmp_path):
    body = "const a = x?.[0];\nfoo(...[1, 2]);\nconst re = /\\.[a]/;\n"
    p = _write(tmp_path, body)
    assert not fix_js_dot_bracket_access(str(p), 'SyntaxError: Unexpected token (1:1)')
    assert p.read_text() == body


def test_dot_bracket_gated_on_error_output(tmp_path):
    p = _write(tmp_path, "const id = todos.[0];\n")
    assert not fix_js_dot_bracket_access(str(p), 'some other failure')


# ── diagnose: the banner must not shadow the Babel detail ─────────────────────

_JEST_OUTPUT = """\
FAIL ./todo.test.js
  ● Test suite failed to run

    Jest encountered an unexpected token

    This usually means that you are trying to import a file which Jest cannot parse, e.g. it's not plain JavaScript.

    Details:

    SyntaxError: /tmp/x/todo.test.js: Identifier 'todos' has already been declared. (38:10)
"""


def test_distill_prefers_babel_detail_over_jest_banner():
    focus = distill_test_errors(_JEST_OUTPUT)
    assert "duplicate 'const todos'" in focus
    assert 'could not parse' not in focus  # banner hint demoted


def test_distill_generic_babel_shape():
    out = "    SyntaxError: /tmp/x/todo-test.js: Missing semicolon. (32:107)"
    focus = distill_test_errors(out)
    assert '/tmp/x/todo-test.js:32' in focus
    assert 'Missing semicolon' in focus


def test_distill_banner_kept_when_nothing_specific():
    focus = distill_test_errors("    Jest encountered an unexpected token\n")
    assert 'could not parse' in focus


def test_distill_real_esm_case():
    out = "    SyntaxError: Cannot use import statement outside a module"
    focus = distill_test_errors(out)
    assert 'CommonJS' in focus
