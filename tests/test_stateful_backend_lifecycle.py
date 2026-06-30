"""Tests for stateful-backend-lifecycle challenge.

Illustrates stateful backend lifecycle issues: state leaks across tests,
setup/teardown missing, etc.
"""
import textwrap

import pytest

class TestStatefulBackendLifecycle:
    """Test scenarios illustrating stateful backend lifecycle challenges."""

    def test_state_leak_across_tests(self, tmp_path):
        """Tests that leak state between each other."""
        (tmp_path / 'test_database.py').write_text(textwrap.dedent("""\
            # Shared database connection that leaks state
            connection = None
            
            def test_first_operation():
                global connection
                connection = create_database_connection()
                # Insert test data
                connection.execute("INSERT INTO users (name) VALUES ('test_user')")
                
                # Verify data exists
                result = connection.query("SELECT COUNT(*) FROM users WHERE name = 'test_user'")
                assert result[0][0] == 1
            
            def test_second_operation():
                # Uses the same connection from previous test - state leaked!
                global connection
                if connection is None:
                    connection = create_database_connection()
                
                # This test expects clean database but finds data from previous test
                result = connection.query("SELECT COUNT(*) FROM users")
                assert result[0][0] == 0  # This will fail because test_user still exists
        """))
        
        content = (tmp_path / 'test_database.py').read_text()
        assert 'global connection' in content
        assert 'test_first_operation' in content
        assert 'test_second_operation' in content
        # Second test will fail due to state leaked from first test

    def test_missing_setup_teardown(self, tmp_path):
        """Tests missing setup and teardown methods."""
        (tmp_path / 'test_api.py').write_text(textwrap.dedent("""\
            # No setup to initialize test data
            # No teardown to clean up after tests
            
            def test_api_call():
                # This test assumes API server is running and data is in known state
                response = requests.get('http://localhost:8080/api/data')
                assert response.status_code == 200
                
                # No cleanup of any data created by the test
                # Next test run might find leftover data
            
            def test_another_api_call():
                # This test might fail if previous test left server in bad state
                response = requests.post('http://localhost:8080/api/data', json={"id": 1})
                assert response.status_code == 201
        """))
        
        content = (tmp_path / 'test_api.py').read_text()
        assert 'def test_api_call' in content
        assert 'def test_another_api_call' in content
        assert 'def setup' not in content
        assert 'def teardown' not in content
        # Missing setup/teardown can cause state leaks

    def test_shared_global_state(self, tmp_path):
        """Tests sharing mutable global state."""
        (tmp_path / 'test_shared.py').write_text(textwrap.dedent("""\
            # Global state shared across all tests
            test_data = []
            
            def test_first():
                test_data.append('first')
                assert len(test_data) == 1
                assert test_data[0] == 'first'
            
            def test_second():
                # test_data still contains 'first' from previous test
                test_data.append('second')
                assert len(test_data) == 1  # This will fail because length is 2
                assert test_data[0] == 'second'  # This will also fail
        """))
        
        content = (tmp_path / 'test_shared.py').read_text()
        assert 'test_data = []' in content
        assert 'test_first' in content
        assert 'test_second' in content
        # Shared mutable state causes tests to depend on each other

    def test_database_transactions_not_rolled_back(self, tmp_path):
        """Database tests with transactions that aren't rolled back."""
        (tmp_path / 'test_db_transactions.py').write_text(textwrap.dedent("""\
            def test_user_creation():
                connection = get_db_connection()
                cursor = connection.cursor()
                
                # Start transaction but never commit or rollback
                cursor.execute("BEGIN")
                cursor.execute("INSERT INTO users (name, email) VALUES ('test', 'test@example.com')")
                
                # Test passes but transaction is left open
                # Next test might see this uncommitted data or hit lock issues
            
            def test_user_listing():
                connection = get_db_connection()
                cursor = connection.cursor()
                
                # This might see the uncommitted user from previous test
                cursor.execute("SELECT * FROM users WHERE name = 'test'")
                users = cursor.fetchall()
                assert len(users) == 0  # Might fail if previous test's transaction is still open
        """))
        
        content = (tmp_path / 'test_db_transactions.py').read_text()
        assert 'BEGIN' in content
        assert 'INSERT INTO users' in content
        # Open transactions can affect subsequent tests