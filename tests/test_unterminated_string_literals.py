"""Tests for unterminated-string-literals challenge.

Illustrates unterminated string literal errors across languages.
"""
import textwrap

import pytest

class TestUnterminatedStringLiterals:
    """Test scenarios illustrating unterminated string literal challenges."""

    def test_python_unterminated_single_quote(self, tmp_path):
        """Python code with unterminated single-quoted string."""
        (tmp_path / 'main.py').write_text(textwrap.dedent("""\
            def main():
                name = 'John
                print(f"Hello, {name}")
        """))
        
        content = (tmp_path / 'main.py').read_text()
        assert "'John" in content
        # Unterminated single-quoted string - missing closing quote

    def test_python_unterminated_double_quote(self, tmp_path):
        """Python code with unterminated double-quoted string."""
        (tmp_path / 'main.py').write_text(textwrap.dedent("""\
            def main():
                message = "Hello, World
                print(message)
        """))
        
        content = (tmp_path / 'main.py').read_text()
        assert '"Hello, World' in content
        # Unterminated double-quoted string - missing closing quote

    def test_python_unterminated_triple_quote(self, tmp_path):
        """Python code with unterminated triple-quoted string."""
        (tmp_path / 'main.py').write_text(textwrap.dedent("""\
            def main():
                docstring = \"\"\"This is a multi-line string
                without proper termination
                print(docstring)
        """))
        
        content = (tmp_path / 'main.py').read_text()
        assert '"""This is a multi-line string' in content
        # Unterminated triple-quoted string - missing closing quotes

    def test_c_unterminated_string(self, tmp_path):
        """C code with unterminated string literal."""
        (tmp_path / 'main.c').write_text(textwrap.dedent("""\
            #include <stdio.h>
            
            int main() {
                char* message = "Hello, World;
                printf("%s\\n", message);
                return 0;
            }
        """))
        
        content = (tmp_path / 'main.c').read_text()
        assert '"Hello, World' in content
        # Unterminated string literal in C - missing closing quote

    def test_javascript_unterminated_template_literal(self, tmp_path):
        """JavaScript code with unterminated template literal."""
        (tmp_path / 'app.js').write_text(textwrap.dedent("""\
            function greet(name) {
                const message = `Hello, ${name
                console.log(message);
            }
        """))
        
        content = (tmp_path / 'app.js').read_text()
        assert '`Hello, ${name' in content
        # Unterminated template literal - missing closing backtick