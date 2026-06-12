"""Regression: stuttered duplicate C# method-signature openers are removed.

Dominant bucket of the 2026-06-12 run-4 collection (4 sessions): the model
emits `public void TestFibonacciSequence() {` three or four times, with
orphaned [Fact] attributes between, before the body arrives — CS1513/CS0111
storms the repair loop never recovered from.
"""

from pathlib import Path

from mu.reflexes.csharp import fix_csharp_consecutive_duplicate_signatures

CORRUPTED = """using Xunit;

public class FibonacciTests
{
    [Fact]
    public void TestFibonacciSequence() {
    public void TestFibonacciSequence() {
        [Fact]
    public void TestFibonacciSequence() {
        Assert.Equal(8, Program.Fibonacci(6));
    }
}
"""

CLEAN = """using Xunit;

public class FibonacciTests
{
    [Fact]
    public void TestOne() {
        Assert.True(true);
    }

    [Fact]
    public void TestTwo() {
        Assert.False(false);
    }
}
"""


def _apply(tmp_path: Path, content: str) -> tuple[bool, str]:
    f = tmp_path / 'FibonacciTests.cs'
    f.write_text(content)
    changed = fix_csharp_consecutive_duplicate_signatures(str(f))
    return changed, f.read_text()


def test_stuttered_openers_collapsed(tmp_path: Path):
    changed, text = _apply(tmp_path, CORRUPTED)
    assert changed
    assert text.count('public void TestFibonacciSequence() {') == 1
    assert text.count('[Fact]') == 1  # the orphaned one went with its dup
    assert 'Assert.Equal(8' in text  # body intact


def test_clean_file_untouched(tmp_path: Path):
    changed, text = _apply(tmp_path, CLEAN)
    assert not changed
    assert text == CLEAN


def test_distinct_overloads_kept(tmp_path: Path):
    src = ('public class C {\n'
           '    public void Run(int n) {\n'
           '    }\n'
           '    public void Run(string s) {\n'
           '    }\n'
           '}\n')
    changed, text = _apply(tmp_path, src)
    assert not changed
    assert text == src


def test_legit_duplicate_with_bodies_untouched(tmp_path: Path):
    # Identical signatures with real bodies between are CS0111, but removing
    # one would delete code — that's the compiler's error to report, not ours.
    src = ('public class C {\n'
           '    public void Run() {\n'
           '        DoA();\n'
           '    }\n'
           '    public void Run() {\n'
           '        DoB();\n'
           '    }\n'
           '}\n')
    changed, text = _apply(tmp_path, src)
    assert not changed
    assert text == src
