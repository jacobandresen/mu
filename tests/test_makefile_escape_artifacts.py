"""Tests for makefile-escape-artifacts challenge.

Illustrates Makefile escape issues, tab requirements, variable expansion.
"""
import textwrap

import pytest

class TestMakefileEscapeArtifacts:
    """Test scenarios illustrating Makefile escape artifact challenges."""

    def test_literal_newline_in_recipe(self, tmp_path):
        """Makefile with literal newline characters in recipe."""
        (tmp_path / 'Makefile').write_text(textwrap.dedent("""\
            target:
            \t@echo "Line 1\\nLine 2"
        """))
        
        content = (tmp_path / 'Makefile').read_text()
        assert '\\n' in content
        # Literal \\n in makefile recipes don't create actual newlines

    def test_escaped_dollar_signs(self, tmp_path):
        """Makefile with escaped dollar signs that should be variables."""
        (tmp_path / 'Makefile').write_text(textwrap.dedent("""\
            VERSION = 1.0
            
            target:
            \t@echo "Version: $$VERSION"
        """))
        
        content = (tmp_path / 'Makefile').read_text()
        assert '$$VERSION' in content
        # $$ should be $ for variable expansion, but escaped incorrectly

    def test_missing_tabs_in_recipes(self, tmp_path):
        """Makefile with spaces instead of tabs in recipes."""
        (tmp_path / 'Makefile').write_text(textwrap.dedent("""\
            target:
                @echo "This should use tabs, not spaces"
        """))
        
        content = (tmp_path / 'Makefile').read_text()
        # The recipe line uses spaces instead of the required tab
        lines = content.split('\n')
        recipe_line = [line for line in lines if '@echo' in line][0]
        assert recipe_line.startswith('    ')  # Shows it's using spaces, not tab

    def test_backslash_continuation_artifacts(self, tmp_path):
        """Makefile with backslash continuation artifacts."""
        (tmp_path / 'Makefile').write_text(textwrap.dedent("""\
            CFLAGS = \\
            \t-Wall \\
            \t-Wextra \\
            \t-O2
            
            target: main.c
            \t$(CC) $(CFLAGS) -o target main.c
        """))
        
        content = (tmp_path / 'Makefile').read_text()
        assert '\\' in content  # Contains backslash continuations
        # Backslash continuations can leave artifacts in generated makefiles