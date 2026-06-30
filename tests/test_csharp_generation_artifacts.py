"""Tests for csharp-generation-artifacts challenge."""
from pathlib import Path

import pytest


class TestCSharpGenerationArtifacts:
    """C# generation artifact scenarios."""

    def test_top_level_statements_before_namespace(self, tmp_path):
        """Top-level statements before namespace."""
        (tmp_path / 'Program.cs').write_text('Console.WriteLine("Hello");\n\nnamespace MyApp\n{\n    class Program\n    {\n        static void Main() { Console.WriteLine("World"); }\n    }\n}')
        content = (tmp_path / 'Program.cs').read_text()
        assert 'Console.WriteLine("Hello")' in content
        assert 'namespace MyApp' in content

    def test_verbatim_string_escaping(self, tmp_path):
        """Verbatim string escaping issues."""
        (tmp_path / 'Program.cs').write_text('class Program\n{\n    static void Main()\n    {\n        string path = @"C:\\Users\\test\\file.txt\n        Console.WriteLine(path);\n    }\n}')
        content = (tmp_path / 'Program.cs').read_text()
        assert '@"C:' in content

    def test_stray_keyword_prefixes(self, tmp_path):
        """Stray @ prefixes on non-keywords."""
        (tmp_path / 'Program.cs').write_text('class Program\n{\n    static void Main()\n    {\n        @int x = 5;\n        @string name = "test";\n    }\n}')
        content = (tmp_path / 'Program.cs').read_text()
        assert '@int' in content
        assert '@string' in content

    def test_lambda_brace_confusion(self, tmp_path):
        """Confused lambda braces."""
        (tmp_path / 'Program.cs').write_text('using System;\nusing System.Linq;\nclass Program\n{\n    static void Main()\n    {\n        var numbers = new int[] { 1, 2, 3 };\n        var result = numbers.Select(x => { return x * 2; });\n    }\n}')
        content = (tmp_path / 'Program.cs').read_text()
        assert 'x => { return x * 2;' in content