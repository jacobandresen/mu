"""Tests for missing-imports challenge.

Illustrates missing import errors across multiple languages.
"""
import textwrap
from pathlib import Path

import pytest

class TestMissingImports:
    """Test scenarios illustrating missing import challenges."""

    def test_python_missing_stdlib_import(self, tmp_path):
        """Python code using stdlib module without import."""
        (tmp_path / 'main.py').write_text(textwrap.dedent("""\
            # This file uses os.getcwd() and path.join() but has no import statements
            current_dir = os.getcwd()
            full_path = path.join('/tmp', 'file.txt')
            
            def main():
                print(f"Current directory: {current_dir}")
                print(f"Full path: {full_path}")
        """))
        
        content = (tmp_path / 'main.py').read_text()
        assert 'os.getcwd()' in content
        assert 'path.join' in content
        # The file uses os and path but has no import statements
        lines = content.split('\n')
        import_lines = [line for line in lines if line.strip().startswith(('import ', 'from ')) and not line.strip().startswith('#')]
        assert len(import_lines) == 0  # No import statements
        # Missing imports for os and path modules

    def test_python_missing_thirdparty_import(self, tmp_path):
        """Python code using third-party library without import."""
        (tmp_path / 'main.py').write_text(textwrap.dedent("""\
            # Missing import flask
            app = Flask(__name__)
            
            @app.route('/')
            def hello():
                return 'Hello, World!'
            
            if __name__ == '__main__':
                app.run()
        """))
        
        content = (tmp_path / 'main.py').read_text()
        assert 'Flask(__name__)' in content
        assert '@app.route' in content
        # Check that there are no flask imports (the flask usage is in code, not imports)
        lines = content.split('\n')
        flask_imports = [line for line in lines if line.strip().startswith(('import flask', 'from flask')) and not line.strip().startswith('#')]
        assert len(flask_imports) == 0  # No flask import statements

    def test_csharp_missing_using(self, tmp_path):
        """C# code using types without proper using directives."""
        (tmp_path / 'Program.cs').write_text(textwrap.dedent("""\
            class Program
            {
                static void Main()
                {
                    // Missing using System;
                    Console.WriteLine("Hello");
                    
                    // Missing using System.Collections.Generic;
                    List<int> numbers = new List<int>();
                }
            }
        """))
        
        content = (tmp_path / 'Program.cs').read_text()
        assert 'Console.WriteLine' in content
        assert 'List<int>' in content
        # Check that there are no using directives
        lines = content.split('\n')
        using_lines = [line for line in lines if line.strip().startswith('using ')]
        assert len(using_lines) == 0  # No using directives

    def test_javascript_missing_require(self, tmp_path):
        """JavaScript code using modules without require/import."""
        (tmp_path / 'app.js').write_text(textwrap.dedent("""\
            // Missing require for fs
            const data = fs.readFileSync('data.txt', 'utf8');
            const filePath = path.join(__dirname, 'files');
            
            console.log(`Path: ${filePath}, Data: ${data}`);
        """))
        
        content = (tmp_path / 'app.js').read_text()
        assert 'fs.readFileSync' in content
        assert 'path.join' in content
        # Check that there are no require or import statements (only comments)
        lines = content.split('\n')
        import_lines = [line for line in lines if line.strip().startswith(('require', 'import')) and not line.strip().startswith('//')]
        assert len(import_lines) == 0  # No import statements
        # Missing module imports for Node.js core modules