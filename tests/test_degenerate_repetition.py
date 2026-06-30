"""Tests for degenerate-repetition challenge."""
from pathlib import Path

import pytest


class TestDegenerateRepetition:
    """Degenerate repetition scenarios."""

    def test_repetitive_import_statements(self, tmp_path):
        """Repetitive imports."""
        (tmp_path / 'main.py').write_text('import os\nimport os\nimport sys\nimport sys\n')
        content = (tmp_path / 'main.py').read_text()
        assert content.count('import os') >= 2
        assert content.count('import sys') >= 2

    def test_looping_code_patterns(self, tmp_path):
        """Looping patterns."""
        (tmp_path / 'main.py').write_text('def process():\n    x = 0\n    while x < 10:\n        x = x + 1\n        x = x - 1\n        x = x + 1\n        x = x - 1\n')
        content = (tmp_path / 'main.py').read_text()
        assert content.count('x = x + 1') >= 2

    def test_redundant_function_calls(self, tmp_path):
        """Redundant calls."""
        (tmp_path / 'main.py').write_text('def get_value():\n    return 42\n\ndef main():\n    x = get_value()\n    x = get_value()\n    x = get_value()\n')
        content = (tmp_path / 'main.py').read_text()
        assert content.count('get_value()') >= 3

    def test_repetitive_try_except_blocks(self, tmp_path):
        """Repetitive error handling."""
        (tmp_path / 'main.py').write_text('def process_data(data):\n    try:\n        result = data * 2\n    except:\n        result = 0\n    try:\n        result = data * 2\n    except:\n        result = 0\n')
        content = (tmp_path / 'main.py').read_text()
        assert content.count('try:') >= 2