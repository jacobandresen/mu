"""Tests for repair-context-budget challenge.

Illustrates repair context budget issues: window bounds prompt AND generation,
large skill stacks, accumulated repair history overflow.
"""
import textwrap

import pytest

class TestRepairContextBudget:
    """Test scenarios illustrating repair context budget challenges."""

    def test_large_skill_stack_overflow(self, tmp_path):
        """Repair context with too many skills loaded."""
        # Simulate a scenario where many skills are loaded
        large_plan = textwrap.dedent("""\
            # Large plan with many steps that would load many skills
            Step 1: Analyze the problem
            Step 2: Choose approach
            Step 3: Implement feature A
            Step 4: Implement feature B
            Step 5: Implement feature C
            Step 6: Implement feature D
            Step 7: Implement feature E
            Step 8: Implement feature F
            Step 9: Implement feature G
            Step 10: Implement feature H
            Step 11: Add error handling
            Step 12: Add validation
            Step 13: Add tests
            Step 14: Add documentation
            Step 15: Review and refine
        """)
        
        (tmp_path / 'PLAN.md').write_text(large_plan)
        
        content = (tmp_path / 'PLAN.md').read_text()
        assert content.count('Step') >= 10
        # Large plans can exceed the context budget for the repair loop

    def test_long_repair_history(self, tmp_path):
        """Repair session with accumulated history that exceeds budget."""
        repair_log = textwrap.dedent("""\
            Repair iteration 1: Fixed import error
            Repair iteration 2: Fixed syntax error
            Repair iteration 3: Fixed type mismatch
            Repair iteration 4: Fixed missing dependency
            Repair iteration 5: Fixed logic error
            Repair iteration 6: Fixed test failure
            Repair iteration 7: Fixed integration issue
            Repair iteration 8: Fixed edge case
            Repair iteration 9: Fixed performance issue
            Repair iteration 10: Fixed memory leak
        """)
        
        (tmp_path / 'repair_history.txt').write_text(repair_log)
        
        content = (tmp_path / 'repair_history.txt').read_text()
        assert content.count('Repair iteration') >= 10
        # Long repair histories can exceed the context budget

    def test_window_bounds_exceeded(self, tmp_path):
        """Repair window that exceeds context bounds."""
        large_code = textwrap.dedent("""\
            def very_long_function_name_that_exceeds_reasonable_length_and_contributes_to_context_budget():
                # Very long function with many lines that would contribute to context budget
                # Many lines of code
                print("Line 1: This is a very long line that contributes to the context budget problem")
                print("Line 2: Another long line for context budget testing purposes")
                print("Line 3: Yet another long line to demonstrate context budget constraints")
                print("Line 4: More lines showing the context budget issue")
                print("Line 5: Even more lines for testing")
                print("Line 6: Additional lines to illustrate the problem")
                print("Line 7: Final line for context budget testing")
        """)
        
        (tmp_path / 'large_module.py').write_text(large_code)
        
        content = (tmp_path / 'large_module.py').read_text()
        assert content.count('Line') >= 5  # At least some lines should be present
        # Large code windows can exceed the repair context budget

    def test_skill_loading_cascade(self, tmp_path):
        """Multiple skills loaded in cascade causing context overflow."""
        skill_files = ['skill_python.md', 'skill_javascript.md', 'skill_csharp.md', 
                      'skill_go.md', 'skill_rust.md', 'skill_makefile.md', 
                      'skill_docker.md', 'skill_github.md', 'skill_web.md']
        
        for skill in skill_files:
            (tmp_path / skill).write_text(f"# {skill}\n\nSkill content for {skill}\n")
        
        # Verify many skills are present
        skill_count = len([f for f in (tmp_path).iterdir() if f.name.startswith('skill_')])
        assert skill_count >= 8
        # Loading too many skills can exceed the context budget for repairs