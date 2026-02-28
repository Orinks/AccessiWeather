from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from accessiweather.config.import_export import ImportExportOperations
from accessiweather.config.portable_secrets import (
    PortableSecretsError,
    decrypt_secret_bundle,
    encrypt_secret_bundle,
)


def test_encrypt_decrypt_secret_bundle_round_trip():
    secrets = {"openrouter_api_key": "sk-test", "visual_crossing_api_key": "vc-test"}

    envelope = encrypt_secret_bundle(secrets, "correct horse battery staple")
    restored = decrypt_secret_bundle(envelope, "correct horse battery staple")

    assert envelope["version"] == 1
    assert envelope["kdf"]["name"] == "pbkdf2-sha256"
    assert restored == secrets


def test_decrypt_secret_bundle_wrong_passphrase_fails():
    envelope = encrypt_secret_bundle({"openrouter_api_key": "sk-test"}, "right-passphrase")

    try:
        decrypt_secret_bundle(envelope, "wrong-passphrase")
        raise AssertionError("Expected decryption failure")
    except PortableSecretsError as exc:
        assert "Invalid passphrase" in str(exc)


def test_decrypt_secret_bundle_unknown_version_fails():
    envelope = encrypt_secret_bundle({"openrouter_api_key": "sk-test"}, "passphrase")
    envelope["version"] = 999

    try:
        decrypt_secret_bundle(envelope, "passphrase")
        raise AssertionError("Expected version validation failure")
    except PortableSecretsError as exc:
        assert "Unsupported encrypted bundle version" in str(exc)


class TestPortableSecretsImportExportWiring:
    def test_export_import_encrypted_api_keys_uses_secure_storage(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"
        imported_store: dict[str, str] = {}

        def _fake_get_password(key_name: str) -> str | None:
            return {
                "openrouter_api_key": "sk-exported",
                "visual_crossing_api_key": "vc-exported",
            }.get(key_name)

        def _fake_set_password(key_name: str, value: str) -> bool:
            imported_store[key_name] = value
            return True

        with (
            patch(
                "accessiweather.config.import_export.SecureStorage.get_password", _fake_get_password
            ),
            patch(
                "accessiweather.config.import_export.SecureStorage.set_password", _fake_set_password
            ),
        ):
            assert operations.export_encrypted_api_keys(export_file, "bundle-pass") is True
            assert export_file.exists()

            saved = json.loads(export_file.read_text(encoding="utf-8"))
            assert saved["version"] == 1

            assert operations.import_encrypted_api_keys(export_file, "bundle-pass") is True

        assert imported_store["openrouter_api_key"] == "sk-exported"
        assert imported_store["visual_crossing_api_key"] == "vc-exported"
        # After import, in-memory config should be refreshed so keys are active immediately
        manager._load_secure_keys.assert_called_once()

    def test_export_encrypted_api_keys_returns_false_when_no_keys(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"

        with patch(
            "accessiweather.config.import_export.SecureStorage.get_password",
            lambda _key_name: None,
        ):
            assert operations.export_encrypted_api_keys(export_file, "bundle-pass") is False

    def test_import_encrypted_api_keys_rejects_non_dict_bundle(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"
        export_file.write_text("[]", encoding="utf-8")

        with patch("accessiweather.config.import_export.SecureStorage.set_password") as mock_set:
            assert operations.import_encrypted_api_keys(export_file, "bundle-pass") is False
            mock_set.assert_not_called()

    def test_import_encrypted_api_keys_returns_false_when_no_supported_keys(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"
        envelope = encrypt_secret_bundle({"other": "value"}, "right-pass")
        export_file.write_text(json.dumps(envelope), encoding="utf-8")

        with patch("accessiweather.config.import_export.SecureStorage.set_password") as mock_set:
            assert operations.import_encrypted_api_keys(export_file, "right-pass") is False
            mock_set.assert_not_called()

    def test_import_encrypted_api_keys_wrong_passphrase_returns_false(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"
        envelope = encrypt_secret_bundle({"openrouter_api_key": "sk-exported"}, "right-pass")
        export_file.write_text(json.dumps(envelope), encoding="utf-8")

        with patch("accessiweather.config.import_export.SecureStorage.set_password") as mock_set:
            assert operations.import_encrypted_api_keys(export_file, "wrong-pass") is False
            mock_set.assert_not_called()


class TestExportEncryptedApiKeysConfigFallback:
    """export_encrypted_api_keys falls back to config.ini when keyring has nothing."""

    def _make_manager(self, settings_dict: dict):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        settings = MagicMock()
        for k, v in settings_dict.items():
            setattr(settings, k, v)
        config = MagicMock()
        config.settings = settings
        manager.get_config.return_value = config
        return manager

    def test_export_uses_config_ini_fallback_when_keyring_empty(self, tmp_path):
        """Keys only in config.ini (not keyring) are still exported."""
        manager = self._make_manager(
            {
                "openrouter_api_key": "sk-from-config",
                "visual_crossing_api_key": "",
            }
        )
        operations = ImportExportOperations(manager)
        export_file = tmp_path / "keys.keys"

        with patch(
            "accessiweather.config.import_export.SecureStorage.get_password",
            lambda _key_name: None,
        ):
            result = operations.export_encrypted_api_keys(export_file, "pass")

        assert result is True
        assert export_file.exists()
        envelope = json.loads(export_file.read_text(encoding="utf-8"))
        secrets = decrypt_secret_bundle(envelope, "pass")
        assert secrets["openrouter_api_key"] == "sk-from-config"
        assert "visual_crossing_api_key" not in secrets

    def test_export_keyring_value_takes_priority_over_config_ini(self, tmp_path):
        """Keyring value wins over config.ini value when both exist."""
        manager = self._make_manager(
            {"openrouter_api_key": "sk-from-config", "visual_crossing_api_key": ""}
        )
        operations = ImportExportOperations(manager)
        export_file = tmp_path / "keys.keys"

        with patch(
            "accessiweather.config.import_export.SecureStorage.get_password",
            lambda key_name: "sk-from-keyring" if key_name == "openrouter_api_key" else None,
        ):
            result = operations.export_encrypted_api_keys(export_file, "pass")

        assert result is True
        secrets = decrypt_secret_bundle(json.loads(export_file.read_text()), "pass")
        assert secrets["openrouter_api_key"] == "sk-from-keyring"

    def test_export_returns_false_when_keyring_and_config_both_empty(self, tmp_path):
        """No keys anywhere → returns False."""
        manager = self._make_manager({"openrouter_api_key": "", "visual_crossing_api_key": None})
        operations = ImportExportOperations(manager)
        export_file = tmp_path / "keys.keys"

        with patch(
            "accessiweather.config.import_export.SecureStorage.get_password",
            lambda _key_name: None,
        ):
            result = operations.export_encrypted_api_keys(export_file, "pass")

        assert result is False
        assert not export_file.exists()
