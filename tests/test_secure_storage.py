"""Tests for secure storage functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from accessiweather.config.secure_storage import LazySecureStorage, SecureStorage


class TestSecureStorage:
    """Tests for SecureStorage class."""

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_set_password_success(self, mock_get_keyring):
        """Test successful password storage."""
        mock_keyring = MagicMock()
        mock_get_keyring.return_value = mock_keyring

        result = SecureStorage.set_password("test_user", "test_password")

        assert result is True
        mock_keyring.set_password.assert_called_once_with(
            "accessiweather", "test_user", "test_password"
        )

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_set_password_keyring_unavailable(self, mock_get_keyring):
        """Test password storage when keyring is unavailable."""
        mock_get_keyring.return_value = None

        result = SecureStorage.set_password("test_user", "test_password")

        assert result is False

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_set_password_empty_calls_delete(self, mock_get_keyring):
        """Test that setting empty password calls delete instead."""
        mock_keyring = MagicMock()
        mock_get_keyring.return_value = mock_keyring

        with patch.object(SecureStorage, 'delete_password', return_value=True) as mock_delete:
            result = SecureStorage.set_password("test_user", "")

            assert result is True
            mock_delete.assert_called_once_with("test_user")
            mock_keyring.set_password.assert_not_called()

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_set_password_exception(self, mock_get_keyring):
        """Test password storage with keyring exception."""
        mock_keyring = MagicMock()
        mock_keyring.set_password.side_effect = Exception("Keyring error")
        mock_get_keyring.return_value = mock_keyring

        result = SecureStorage.set_password("test_user", "test_password")

        assert result is False

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_get_password_success(self, mock_get_keyring):
        """Test successful password retrieval."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "test_password"
        mock_get_keyring.return_value = mock_keyring

        result = SecureStorage.get_password("test_user")

        assert result == "test_password"
        mock_keyring.get_password.assert_called_once_with("accessiweather", "test_user")

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_get_password_keyring_unavailable(self, mock_get_keyring):
        """Test password retrieval when keyring is unavailable."""
        mock_get_keyring.return_value = None

        result = SecureStorage.get_password("test_user")

        assert result is None

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_get_password_exception(self, mock_get_keyring):
        """Test password retrieval with keyring exception."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.side_effect = Exception("Keyring error")
        mock_get_keyring.return_value = mock_keyring

        result = SecureStorage.get_password("test_user")

        assert result is None

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_delete_password_success(self, mock_get_keyring):
        """Test successful password deletion."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = "existing_password"
        mock_get_keyring.return_value = mock_keyring

        result = SecureStorage.delete_password("test_user")

        assert result is True
        mock_keyring.get_password.assert_called_once_with("accessiweather", "test_user")
        mock_keyring.delete_password.assert_called_once_with("accessiweather", "test_user")

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_delete_password_not_exists(self, mock_get_keyring):
        """Test password deletion when password doesn't exist."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.return_value = None
        mock_get_keyring.return_value = mock_keyring

        result = SecureStorage.delete_password("test_user")

        assert result is True
        mock_keyring.get_password.assert_called_once_with("accessiweather", "test_user")
        mock_keyring.delete_password.assert_not_called()

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_delete_password_keyring_unavailable(self, mock_get_keyring):
        """Test password deletion when keyring is unavailable."""
        mock_get_keyring.return_value = None

        result = SecureStorage.delete_password("test_user")

        assert result is True

    @patch("accessiweather.config.secure_storage._get_keyring")
    def test_delete_password_exception(self, mock_get_keyring):
        """Test password deletion with keyring exception."""
        mock_keyring = MagicMock()
        mock_keyring.get_password.side_effect = Exception("Keyring error")
        mock_get_keyring.return_value = mock_keyring

        result = SecureStorage.delete_password("test_user")

        assert result is False


class TestLazySecureStorage:
    """Tests for LazySecureStorage class."""

    def test_init(self):
        """Test LazySecureStorage initialization."""
        lazy_storage = LazySecureStorage("test_key")

        assert lazy_storage._key_name == "test_key"
        assert lazy_storage._value is None
        assert lazy_storage._loaded is False

    @patch.object(SecureStorage, 'get_password', return_value="test_value")
    def test_value_loads_from_keyring(self, mock_get_password):
        """Test that value property loads from keyring on first access."""
        lazy_storage = LazySecureStorage("test_key")

        result = lazy_storage.value

        assert result == "test_value"
        assert lazy_storage._loaded is True
        assert lazy_storage._value == "test_value"
        mock_get_password.assert_called_once_with("test_key")

    @patch.object(SecureStorage, 'get_password', return_value="test_value")
    def test_value_cached_after_first_access(self, mock_get_password):
        """Test that value is cached after first access."""
        lazy_storage = LazySecureStorage("test_key")

        # First access
        result1 = lazy_storage.value
        # Second access
        result2 = lazy_storage.value

        assert result1 == result2 == "test_value"
        mock_get_password.assert_called_once()  # Only called once

    @patch.object(SecureStorage, 'get_password', return_value=None)
    def test_value_returns_empty_string_when_none(self, mock_get_password):
        """Test that value returns empty string when keyring returns None."""
        lazy_storage = LazySecureStorage("test_key")

        result = lazy_storage.value

        assert result == ""

    @patch.object(SecureStorage, 'get_password', return_value="test_value")
    def test_str_returns_value(self, mock_get_password):
        """Test that str() returns the value."""
        lazy_storage = LazySecureStorage("test_key")

        result = str(lazy_storage)

        assert result == "test_value"

    @patch.object(SecureStorage, 'get_password', return_value="test_value")
    def test_bool_true_for_non_empty(self, mock_get_password):
        """Test that bool() returns True for non-empty value."""
        lazy_storage = LazySecureStorage("test_key")

        result = bool(lazy_storage)

        assert result is True

    @patch.object(SecureStorage, 'get_password', return_value="")
    def test_bool_false_for_empty(self, mock_get_password):
        """Test that bool() returns False for empty value."""
        lazy_storage = LazySecureStorage("test_key")

        result = bool(lazy_storage)

        assert result is False

    @patch.object(SecureStorage, 'get_password', return_value=None)
    def test_bool_false_for_none(self, mock_get_password):
        """Test that bool() returns False for None value."""
        lazy_storage = LazySecureStorage("test_key")

        result = bool(lazy_storage)

        assert result is False

    @patch.object(SecureStorage, 'get_password', return_value="  test_value  ")
    def test_strip_returns_stripped_value(self, mock_get_password):
        """Test that strip() returns stripped value."""
        lazy_storage = LazySecureStorage("test_key")

        result = lazy_storage.strip()

        assert result == "test_value"

    @patch.object(SecureStorage, 'get_password', return_value="test_value")
    def test_equality_with_string(self, mock_get_password):
        """Test equality comparison with string."""
        lazy_storage = LazySecureStorage("test_key")

        assert lazy_storage == "test_value"
        assert lazy_storage != "different_value"

    @patch.object(SecureStorage, 'get_password')
    def test_equality_with_lazy_storage(self, mock_get_password):
        """Test equality comparison between LazySecureStorage instances."""
        mock_get_password.return_value = "test_value"

        lazy_storage1 = LazySecureStorage("test_key1")
        lazy_storage2 = LazySecureStorage("test_key2")

        assert lazy_storage1 == lazy_storage2

    def test_equality_with_incompatible_type(self):
        """Test equality comparison with incompatible type."""
        lazy_storage = LazySecureStorage("test_key")

        result = lazy_storage.__eq__(123)

        assert result is NotImplemented

    @patch.object(SecureStorage, 'get_password', return_value="test_value")
    def test_reset_clears_cache(self, mock_get_password):
        """Test that reset() clears the cached value."""
        lazy_storage = LazySecureStorage("test_key")

        # Load value
        _ = lazy_storage.value
        assert lazy_storage._loaded is True

        # Reset
        lazy_storage.reset()

        assert lazy_storage._loaded is False
        assert lazy_storage._value is None

        # Access again should reload
        _ = lazy_storage.value
        assert mock_get_password.call_count == 2


class TestKeyringModule:
    """Tests for keyring module lazy loading."""

    def test_get_keyring_caches_result(self):
        """Test that _get_keyring caches the keyring module after first call."""
        from accessiweather.config import secure_storage

        # Reset module state
        secure_storage._keyring_module = None
        secure_storage._keyring_checked = False

        # First call imports keyring (real or mock doesn't matter)
        result1 = secure_storage._get_keyring()
        # Second call should return cached result
        result2 = secure_storage._get_keyring()

        assert result1 is result2
        assert secure_storage._keyring_checked is True

    def test_get_keyring_handles_import_error(self):
        """Test that _get_keyring handles ImportError gracefully."""
        from accessiweather.config import secure_storage

        # Reset module state
        secure_storage._keyring_module = None
        secure_storage._keyring_checked = False

        # Patch the import inside _get_keyring to raise ImportError
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "keyring":
                raise ImportError("No keyring")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = secure_storage._get_keyring()

        assert result is None
        assert secure_storage._keyring_checked is True

        # Restore state for other tests
        secure_storage._keyring_module = None
        secure_storage._keyring_checked = False
