"""Coverage for distill_test_errors grammars added from real archived failures.

Each snippet is a verbatim error line that previously distilled to nothing,
leaving the failure as "(no distilled cause)" in the reflex KB (observe.py).
These assert the distiller now names a cause — no LLM, fully offline.
"""
from mu.diagnose import distill_test_errors


def _focus(text: str) -> str:
    out = distill_test_errors(text)
    assert out, f"expected a FOCUS cause, got nothing for:\n{text}"
    return out


def test_msbuild_no_project_file():
    log = ("MSBUILD : error MSB1003: Specify a project or solution file. "
           "The current working directory does not contain a project or solution file.")
    assert "MSB1003" in _focus(log)


def test_go_syntax_error():
    log = ("# p5-gin\n"
           "./main.go:10:1: syntax error: unexpected ., expected }\n"
           "FAIL\tp5-gin [build failed]")
    f = _focus(log)
    assert "Go syntax error" in f and "main.go:10" in f


def test_vitest_expected_to_contain():
    log = ("   → expected 'Todo ListAdd' to contain 'Buy milk'\n"
           " FAIL  src/App.test.ts > adds a todo")
    f = _focus(log)
    assert "expected" in f and "contain" in f


def test_unrelated_output_still_distills_to_nothing():
    # Guard: the new fluent-assertion rule must not fire on ordinary prose.
    assert distill_test_errors("All tests passed. Nothing to report here.") == ""
