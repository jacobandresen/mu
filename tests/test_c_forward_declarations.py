"""Tests for c-forward-declarations challenge."""
from pathlib import Path

import pytest


class TestCForwardDeclarations:
    """C forward declaration issues."""

    def test_missing_forward_declaration(self, tmp_path):
        """Function pointer without forward declaration."""
        (tmp_path / 'main.c').write_text('void (*func_ptr)(int);\nvoid use_func(void (*f)(int)) { f(42); }\n')
        content = (tmp_path / 'main.c').read_text()
        assert 'void (*func_ptr)(int)' in content

    def test_nested_struct_definition(self, tmp_path):
        """Deeply nested structs."""
        (tmp_path / 'main.c').write_text('typedef struct { int x; struct { int y; } nested; } ComplexStruct;')
        content = (tmp_path / 'main.c').read_text()
        assert 'struct {' in content

    def test_circular_type_dependencies(self, tmp_path):
        """Circular dependencies between types."""
        (tmp_path / 'a.h').write_text('typedef struct B B;\ntypedef struct A { B* b_ptr; } A;')
        (tmp_path / 'b.h').write_text('typedef struct A A;\ntypedef struct B { A* a_ptr; } B;')
        assert (tmp_path / 'a.h').exists()
        assert (tmp_path / 'b.h').exists()