"""Tests for generic-syntax-errors challenge."""
from pathlib import Path

import pytest

from mu.reflexes.python.fix_python_decorator_colon import fix_python_decorator_colon
from mu.reflexes.python.fix_python_missing_def import fix_python_missing_def


class TestGenericSyntaxErrors:
    """Generic syntax error scenarios."""

    def test_python_decorator_colon(self, tmp_path):
        """Decorator with trailing colon - reflex handles this."""
        py_file = tmp_path / 'main.py'
        py_file.write_text('@app.route("/"):\n')
        
        assert fix_python_decorator_colon(str(py_file))
        assert '@app.route("/")' in py_file.read_text()
        assert '@app.route("/"):' not in py_file.read_text()

    def test_python_missing_def(self, tmp_path):
        """Decorator without function - reflex handles this."""
        py_file = tmp_path / 'main.py'
        py_file.write_text('@app.route("/")\n    return "Hello"\n')
        
        assert fix_python_missing_def(str(py_file))
        content = py_file.read_text()
        assert '@app.route("/")' in content
        assert 'def ' in content

    def test_python_unindented_def_scenario(self, tmp_path):
        """def body at wrong indentation - illustrates issue."""
        py_file = tmp_path / 'main.py'
        py_file.write_text('class MyClass:\n    def method(self):\n    pass\n')
        
        content = py_file.read_text()
        assert 'def method(self):\n    pass' in content

    def test_csharp_missing_semicolon_scenario(self, tmp_path):
        """Missing semicolon - illustrates issue."""
        cs_file = tmp_path / 'Program.cs'
        cs_file.write_text('using System;\nclass Program { static void Main() { Console.WriteLine("Hello") } }')
        
        content = cs_file.read_text()
        assert 'Console.WriteLine("Hello")' in content

    def test_javascript_missing_brace_scenario(self, tmp_path):
        """Missing closing brace - illustrates issue."""
        js_file = tmp_path / 'app.js'
        js_file.write_text('function test() {\n  console.log("Hello")\n')
        
        content = js_file.read_text()
        assert content.count('{') > content.count('}')

    def test_go_missing_brace_scenario(self, tmp_path):
        """Missing closing brace - illustrates issue."""
        go_file = tmp_path / 'main.go'
        go_file.write_text('package main\nimport "fmt"\nfunc main() {\n  fmt.Println("Hello")\n')
        
        content = go_file.read_text()
        assert content.count('{') > content.count('}')

    def test_actual_decorator_colon_fix(self, tmp_path):
        """Test decorator colon fix works."""
        py_file = tmp_path / 'main.py'
        py_file.write_text('@app.route("/"):\n')
        
        result = fix_python_decorator_colon(str(py_file))
        assert result is True
        updated = py_file.read_text()
        assert '@app.route("/")' in updated
        assert '@app.route("/"):' not in updated

    def test_actual_missing_def_fix(self, tmp_path):
        """Test missing def fix works."""
        py_file = tmp_path / 'main.py'
        py_file.write_text('@app.route("/")\n    return "Hello"\n')
        
        result = fix_python_missing_def(str(py_file))
        assert result is True
        updated = py_file.read_text()
        assert '@app.route("/")' in updated
        assert 'def ' in updated