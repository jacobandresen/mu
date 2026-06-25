"""Round-7 reflexes, written from run-7 repair-trace data: the CS0017
entry-point conflict (19 FOCUS occurrences, 0 model-resolved) and the
unindented Python body (28 no-FOCUS iterations)."""

from pathlib import Path

from mu.reflexes.csharp import fix_csharp_test_program_conflict
from mu.reflexes.python import fix_python_unindented_body

EXE_TEST_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.*" />
    <PackageReference Include="xunit" Version="2.*" />
  </ItemGroup>
</Project>
"""

BROKEN_FLASK = """from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/todos', methods=['POST'])
def add_todo():
task = request.get_json()['task']
return jsonify({'task': task}), 201

@app.route('/todos', methods=['GET'])
def get_todos():
return jsonify([])
"""

LINT_OUT = ("main.py:7:1: expected an indented block after function definition on line 6\n"
            "main.py:12:1: expected an indented block after function definition on line 11\n")


def test_exe_plus_testsdk_gets_generateprogramfile(tmp_path: Path):
    # The CS0017 case: an Exe with a *user* Main + Test.Sdk ⇒ two entry points.
    (tmp_path / 'app.csproj').write_text(EXE_TEST_CSPROJ)
    (tmp_path / 'Program.cs').write_text(
        'class Program { static void Main(string[] args) { } }\n')
    assert fix_csharp_test_program_conflict(str(tmp_path))
    text = (tmp_path / 'app.csproj').read_text()
    assert '<GenerateProgramFile>false</GenerateProgramFile>' in text
    assert not fix_csharp_test_program_conflict(str(tmp_path))  # idempotent


def test_exe_testsdk_without_user_main_untouched(tmp_path: Path):
    # CS5001 regression: model wrote test files but no Main. Disabling the generated
    # entry point here would leave the Exe with no Main at all — must NOT fire.
    (tmp_path / 'app.csproj').write_text(EXE_TEST_CSPROJ)
    (tmp_path / 'FibonacciTests.cs').write_text(
        'using Xunit;\npublic class T { [Fact] public void A() { Assert.True(true); } }\n')
    assert not fix_csharp_test_program_conflict(str(tmp_path))
    assert 'GenerateProgramFile' not in (tmp_path / 'app.csproj').read_text()


def test_pure_test_project_untouched(tmp_path: Path):
    (tmp_path / 'tests.csproj').write_text(
        EXE_TEST_CSPROJ.replace('<OutputType>Exe</OutputType>\n    ', ''))
    assert not fix_csharp_test_program_conflict(str(tmp_path))


def test_exe_without_testsdk_untouched(tmp_path: Path):
    (tmp_path / 'app.csproj').write_text(
        EXE_TEST_CSPROJ.replace('Microsoft.NET.Test.Sdk', 'SomethingElse'))
    assert not fix_csharp_test_program_conflict(str(tmp_path))


def test_unindented_bodies_fixed(tmp_path: Path):
    f = tmp_path / 'main.py'
    f.write_text(BROKEN_FLASK)
    assert fix_python_unindented_body(str(f), LINT_OUT)
    import ast
    tree = ast.parse(f.read_text())  # must be valid Python now
    text = f.read_text()
    assert "    task = request.get_json()['task']" in text
    assert "    return jsonify([])" in text
    # decorators/defs stayed at column 0
    assert "\n@app.route('/todos', methods=['GET'])" in text


def test_no_matching_lint_message_no_change(tmp_path: Path):
    f = tmp_path / 'main.py'
    f.write_text(BROKEN_FLASK)
    assert not fix_python_unindented_body(str(f), 'main.py:3:1: some other error')
    assert f.read_text() == BROKEN_FLASK


def test_rolls_back_if_result_unparsable(tmp_path: Path):
    f = tmp_path / 'main.py'
    # body line that is itself broken syntax — indenting can't make it parse
    f.write_text("def f():\nreturn ((\n")
    out = fix_python_unindented_body(
        str(f), 'main.py:2:1: expected an indented block after function definition on line 1')
    assert not out
    assert f.read_text() == "def f():\nreturn ((\n"
