"""Tests for environment-hygiene challenge."""
from pathlib import Path

import pytest


class TestEnvironmentHygiene:
    """Environment hygiene scenarios."""

    def test_inconsistent_path_separators(self, tmp_path):
        """Inconsistent path separators."""
        (tmp_path / 'main.py').write_text('import os\ndata_dir = \'data/files\'\noutput_dir = \'output\\\\results\'\n')
        content = (tmp_path / 'main.py').read_text()
        assert 'data/files' in content
        assert 'output\\\\results' in content

    def test_hardcoded_local_paths(self, tmp_path):
        """Hardcoded paths."""
        (tmp_path / 'main.py').write_text('def process_files():\n    data_file = \'/Users/john/Documents/project/data.csv\'\n')
        content = (tmp_path / 'main.py').read_text()
        assert '/Users/john' in content

    def test_relative_import_issues(self, tmp_path):
        """Relative import issues."""
        (tmp_path / 'src').mkdir()
        (tmp_path / 'src' / 'module_a.py').write_text('def function_a():\n    return \'A\'')
        (tmp_path / 'src' / 'module_b.py').write_text('from . import module_a\nfrom ..other import utils')
        assert (tmp_path / 'src' / 'module_a.py').exists()
        assert (tmp_path / 'src' / 'module_b.py').exists()

    def test_missing_shebang_line(self, tmp_path):
        """Missing shebang."""
        (tmp_path / 'script.py').write_text('# Missing shebang\nprint("Hello")')
        content = (tmp_path / 'script.py').read_text()
        assert not content.startswith('#!')