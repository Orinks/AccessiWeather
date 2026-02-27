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

        export_file = tmp_path / "keys.awkeys"
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

    def test_export_encrypted_api_keys_returns_false_when_no_keys(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.awkeys"

        with patch(
            "accessiweather.config.import_export.SecureStorage.get_password",
            lambda _key_name: None,
        ):
            assert operations.export_encrypted_api_keys(export_file, "bundle-pass") is False

    def test_import_encrypted_api_keys_rejects_non_dict_bundle(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.awkeys"
        export_file.write_text("[]", encoding="utf-8")

        with patch("accessiweather.config.import_export.SecureStorage.set_password") as mock_set:
            assert operations.import_encrypted_api_keys(export_file, "bundle-pass") is False
            mock_set.assert_not_called()

    def test_import_encrypted_api_keys_returns_false_when_no_supported_keys(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.awkeys"
        envelope = encrypt_secret_bundle({"other": "value"}, "right-pass")
        export_file.write_text(json.dumps(envelope), encoding="utf-8")

        with patch("accessiweather.config.import_export.SecureStorage.set_password") as mock_set:
            assert operations.import_encrypted_api_keys(export_file, "right-pass") is False
            mock_set.assert_not_called()

    def test_import_encrypted_api_keys_wrong_passphrase_returns_false(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.awkeys"
        envelope = encrypt_secret_bundle({"openrouter_api_key": "sk-exported"}, "right-pass")
        export_file.write_text(json.dumps(envelope), encoding="utf-8")

        with patch("accessiweather.config.import_export.SecureStorage.set_password") as mock_set:
            assert operations.import_encrypted_api_keys(export_file, "wrong-pass") is False
            mock_set.assert_not_called()
