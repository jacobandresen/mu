"""Tests for test-isolation-design challenge.

Illustrates test isolation issues: tests depend on each other,
order-dependent, shared state.
"""
import textwrap

import pytest

class TestTestIsolationDesign:
    """Test scenarios illustrating test isolation design challenges."""

    def test_order_dependent_tests(self, tmp_path):
        """Tests that depend on execution order."""
        (tmp_path / 'test_order.py').write_text(textwrap.dedent("""\
            # Tests that must run in specific order
            
            global state
            state = "initial"
            
            def test_step_one():
                global state
                assert state == "initial"
                state = "after_step_one"
            
            def test_step_two():
                global state
                # This test depends on test_step_one running first
                assert state == "after_step_one"
                state = "after_step_two"
            
            def test_step_three():
                global state
                # This test depends on both previous tests
                assert state == "after_step_two"
                state = "complete"
        """))
        
        content = (tmp_path / 'test_order.py').read_text()
        assert 'global state' in content
        assert 'test_step_one' in content
        assert 'test_step_two' in content
        assert 'test_step_three' in content
        # Tests depend on execution order - violating isolation

    def test_tests_sharing_database_state(self, tmp_path):
        """Tests sharing database state across test functions."""
        (tmp_path / 'test_database.py').write_text(textwrap.dedent("""\
            # Shared database connection
            db = DatabaseConnection("test_db")
            
            def test_create_user():
                # Create a user and leave it in the database
                user_id = db.insert_user("test_user")
                assert user_id > 0
                # No cleanup - user remains for next test
            
            def test_list_users():
                # This test might see users created by other tests
                users = db.query_users()
                assert len(users) == 0  # This fails if test_create_user ran first
        """))
        
        content = (tmp_path / 'test_database.py').read_text()
        assert 'DatabaseConnection' in content
        assert 'test_create_user' in content
        assert 'test_list_users' in content
        # Tests share database state - violating isolation

    def test_tests_depending_on_external_state(self, tmp_path):
        """Tests depending on external system state."""
        (tmp_path / 'test_external.py').write_text(textwrap.dedent("""\
            def test_file_exists():
                # Depends on external file system state
                with open('/tmp/external_file.txt', 'r') as f:
                    content = f.read()
                assert content == "expected_content"
            
            def test_file_content_length():
                # Depends on the same external file and its content
                with open('/tmp/external_file.txt', 'r') as f:
                    content = f.read()
                assert len(content) == 17  # Length of "expected_content"
                # Both tests depend on external file that might change
        """))
        
        content = (tmp_path / 'test_external.py').read_text()
        assert '/tmp/external_file.txt' in content
        assert 'test_file_exists' in content
        assert 'test_file_content_length' in content
        # Tests depend on external state - violating isolation

    def test_tests_with_side_effects(self, tmp_path):
        """Tests that have side effects affecting other tests."""
        (tmp_path / 'test_side_effects.py').write_text(textwrap.dedent("""\
            # Global configuration
            config = {"debug": False}
            
            def test_enable_debug():
                # This test changes global configuration
                config["debug"] = True
                assert config["debug"] is True
            
            def test_debug_disabled():
                # This test expects debug to be disabled
                assert config["debug"] is False
                # Fails if test_enable_debug ran first
            
            def test_check_config():
                # This test might see either state depending on execution order
                if config["debug"]:
                    print("Debug is enabled")
                else:
                    print("Debug is disabled")
        """))
        
        content = (tmp_path / 'test_side_effects.py').read_text()
        assert 'config = {"debug": False}' in content
        assert 'test_enable_debug' in content
        assert 'test_debug_disabled' in content
        # Tests have side effects that affect each other