"""Tests for test-file-syntax-errors challenge.

Illustrates syntax errors specifically in generated test files.
"""
import textwrap

import pytest

class TestTestFileSyntaxErrors:
    """Test scenarios illustrating syntax errors in test files."""

    def test_python_test_file_missing_paren(self, tmp_path):
        """Python test file with missing parenthesis."""
        (tmp_path / 'test_math.py').write_text(textwrap.dedent("""\
            def test_add():
                result = add(2, 3
                assert result == 5
        """))
        
        content = (tmp_path / 'test_math.py').read_text()
        assert 'add(2, 3' in content
        assert 'assert result == 5' in content
        # Missing closing parenthesis in function call

    def test_python_test_file_missing_colon(self, tmp_path):
        """Python test file with missing colon."""
        (tmp_path / 'test_utils.py').write_text(textwrap.dedent("""\
            def test_helper_function()
                result = helper()
                assert result is True
        """))
        
        content = (tmp_path / 'test_utils.py').read_text()
        assert 'def test_helper_function()' in content
        # Missing colon after function definition

    def test_python_test_file_wrong_indentation(self, tmp_path):
        """Python test file with wrong indentation."""
        (tmp_path / 'test_indent.py').write_text(textwrap.dedent("""\
            def test_nested():
            result = get_data()
            assert result is not None
        """))
        
        content = (tmp_path / 'test_indent.py').read_text()
        lines = content.split('\n')
        # Function body should be indented but isn't
        assert any('result = get_data()' in line and not line.startswith(('    ', '\t')) for line in lines)

    def test_csharp_test_file_missing_brace(self, tmp_path):
        """C# test file with missing brace."""
        (tmp_path / 'UnitTest1.cs').write_text(textwrap.dedent("""\
            using Xunit;
            
            namespace MyApp.Tests
            {
                public class UnitTest1
                {
                    [Fact]
                    public void TestAddition()
                    {
                        var result = Calculator.Add(2, 3);
                        Assert.Equal(5, result);
                    
                    [Fact]
                    public void TestSubtraction()
                    {
                        var result = Calculator.Subtract(5, 2);
                        Assert.Equal(3, result);
                }
            }
        """))
        
        content = (tmp_path / 'UnitTest1.cs').read_text()
        # Count braces to show imbalance
        open_braces = content.count('{')
        close_braces = content.count('}')
        assert open_braces != close_braces  # Missing closing brace for TestSubtraction method

    def test_javascript_test_file_syntax_error(self, tmp_path):
        """JavaScript test file with syntax error."""
        (tmp_path / 'math.test.js').write_text(textwrap.dedent("""\
            const { add, subtract } = require('./math');
            
            test('adds numbers', () => {
                expect(add(2, 3)).toBe(5);
            };
            
            test('subtracts numbers', () => {
                expect(subtract(5, 2)).toBe(3);
            }
        """))
        
        content = (tmp_path / 'math.test.js').read_text()
        assert "test('adds numbers', () => {" in content
        assert '.toBe(5)' in content
        # Missing closing parenthesis for the first test function