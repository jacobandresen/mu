"""Tests for build-target-inconsistency challenge."""
from pathlib import Path

import pytest


class TestBuildTargetInconsistency:
    """Build target inconsistency scenarios."""

    def test_binary_name_mismatch(self, tmp_path):
        """Makefile references wrong binary name."""
        (tmp_path / 'main.c').write_text('int main() { return 0; }')
        (tmp_path / 'Makefile').write_text('myapp: main.c\n\tclang -o myapp main.c\n\ntest:\n\t./myapp\n')
        
        content = (tmp_path / 'Makefile').read_text()
        assert 'myapp: main.c' in content
        assert './myapp' in content

    def test_missing_test_recipe(self, tmp_path):
        """Makefile missing test recipe."""
        (tmp_path / 'Makefile').write_text('app: main.c\n\tclang -o app main.c\n')
        
        content = (tmp_path / 'Makefile').read_text()
        assert 'test:' not in content

    def test_files_wrong_directory(self, tmp_path):
        """Files written to wrong directories."""
        (tmp_path / 'tests').mkdir()
        (tmp_path / 'tests' / 'main.py').write_text('print("hello")')
        
        assert (tmp_path / 'tests' / 'main.py').exists()
        assert not (tmp_path / 'src' / 'main.py').exists()

    def test_missing_library_link(self, tmp_path):
        """Makefile missing required library."""
        (tmp_path / 'main.c').write_text('#include <SDL2/SDL.h>\nint main() { return 0; }')
        (tmp_path / 'Makefile').write_text('app: main.c\n\tclang -o app main.c\n')
        
        content = (tmp_path / 'Makefile').read_text()
        assert '-lSDL2' not in content