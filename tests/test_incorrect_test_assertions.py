"""Tests for incorrect-test-assertions challenge."""
from pathlib import Path

import pytest


class TestIncorrectTestAssertions:
    """Incorrect test assertion scenarios."""

    def test_wrong_expected_value(self, tmp_path):
        """Wrong expected value."""
        (tmp_path / 'test_main.py').write_text('def add(a, b):\n    return a + b\n\n\ndef test_add():\n    result = add(2, 3)\n    assert result == 6')
        content = (tmp_path / 'test_main.py').read_text()
        assert 'assert result == 6' in content

    def test_mismatched_selector(self, tmp_path):
        """Mismatched CSS selector."""
        content = 'def test_login_button():\n    # Wrong selector\n    login_button = driver.find_element_by_css_selector(".login-button")\n    assert login_button is not None'
        (tmp_path / 'test_web.py').write_text(content)
        content = (tmp_path / 'test_web.py').read_text()
        assert '.login-button' in content

    def test_asserting_wrong_property(self, tmp_path):
        """Wrong property assertion."""
        (tmp_path / 'test_user.py').write_text('class User:\n    def __init__(self, name, email):\n        self.name = name\n        self.email = email\n\n\ndef test_user_creation():\n    user = User("John", "john@example.com")\n    assert user.name == "john@example.com"')
        content = (tmp_path / 'test_user.py').read_text()
        assert 'user.name == "john@example.com"' in content

    def test_boolean_assertion_inverted(self, tmp_path):
        """Inverted boolean assertion."""
        (tmp_path / 'test_auth.py').write_text('def is_authenticated(user):\n    return user is not None and user.active\n\n\ndef test_guest_user():\n    guest = None\n    assert is_authenticated(guest)')
        content = (tmp_path / 'test_auth.py').read_text()
        assert 'assert is_authenticated(guest)' in content