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
    secrets = {
        "openrouter_api_key": "FAKE_SK_TEST_ONLY",
        "visual_crossing_api_key": "FAKE_VC_TEST_ONLY",
        "pirate_weather_api_key": "FAKE_PW_TEST_ONLY",
    }

    envelope = encrypt_secret_bundle(secrets, "correct horse battery staple")
    restored = decrypt_secret_bundle(envelope, "correct horse battery staple")

    assert envelope["version"] == 1
    assert envelope["kdf"]["name"] == "pbkdf2-sha256"
    assert restored == secrets


def test_decrypt_secret_bundle_wrong_passphrase_fails():
    envelope = encrypt_secret_bundle(
        {"openrouter_api_key": "FAKE_SK_TEST_ONLY"}, "FAKE_RIGHT_PASSPHRASE"
    )

    try:
        decrypt_secret_bundle(envelope, "FAKE_WRONG_PASSPHRASE")
        raise AssertionError("Expected decryption failure")
    except PortableSecretsError as exc:
        assert "Invalid passphrase" in str(exc)


def test_decrypt_secret_bundle_unknown_version_fails():
    envelope = encrypt_secret_bundle(
        {"openrouter_api_key": "FAKE_SK_TEST_ONLY"}, "FAKE_TEST_PASSPHRASE"
    )
    envelope["version"] = 999

    try:
        decrypt_secret_bundle(envelope, "FAKE_TEST_PASSPHRASE")
        raise AssertionError("Expected version validation failure")
    except PortableSecretsError as exc:
        assert "Unsupported encrypted bundle version" in str(exc)


class TestPortableSecretsImportExportWiring:
    def test_export_import_encrypted_api_keys_uses_secure_storage(self, tmp_path):
        """Installed-mode round-trip: export from keyring, import writes both keys."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        manager._config = None  # no in-memory config; export falls through to keyring
        manager.app = None  # not portable; import calls _load_secure_keys
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"
        imported_store: dict[str, str] = {}

        def _fake_get_password(key_name: str) -> str | None:
            return {
                "openrouter_api_key": "FAKE_OR_EXPORTED_TEST",
                "visual_crossing_api_key": "FAKE_VC_EXPORTED_TEST",
                "pirate_weather_api_key": "FAKE_PW_EXPORTED_TEST",
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
            assert (
                operations.export_encrypted_api_keys(export_file, "FAKE_BUNDLE_PASSPHRASE") is True
            )
            assert export_file.exists()

            saved = json.loads(export_file.read_text(encoding="utf-8"))
            assert saved["version"] == 1

            assert (
                operations.import_encrypted_api_keys(export_file, "FAKE_BUNDLE_PASSPHRASE") is True
            )

        assert imported_store["openrouter_api_key"] == "FAKE_OR_EXPORTED_TEST"
        assert imported_store["visual_crossing_api_key"] == "FAKE_VC_EXPORTED_TEST"
        assert imported_store["pirate_weather_api_key"] == "FAKE_PW_EXPORTED_TEST"
        # After import, in-memory config should be refreshed so keys are active immediately
        manager._load_secure_keys.assert_called_once()

    def test_export_encrypted_api_keys_returns_false_when_no_keys(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        manager._config = None  # no in-memory config
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"

        with patch(
            "accessiweather.config.import_export.SecureStorage.get_password",
            lambda _key_name: None,
        ):
            assert (
                operations.export_encrypted_api_keys(export_file, "FAKE_BUNDLE_PASSPHRASE") is False
            )

    def test_export_reads_in_memory_keys_for_portable_mode(self, tmp_path):
        """Portable-mode export: reads keys from settings, not keyring."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        # Simulate in-memory settings with API keys (portable mode)
        config = MagicMock()
        config.settings.visual_crossing_api_key = "FAKE_VC_KEY_TEST"
        config.settings.pirate_weather_api_key = "FAKE_PW_KEY_TEST"
        config.settings.openrouter_api_key = "FAKE_OR_KEY_TEST"
        manager._config = config
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"

        # Keyring returns nothing — keys are only in-memory
        with patch(
            "accessiweather.config.import_export.SecureStorage.get_password",
            lambda _key_name: None,
        ):
            assert operations.export_encrypted_api_keys(export_file, "FAKE_PASSPHRASE_123") is True

        # Decrypt and verify both keys were exported
        saved = json.loads(export_file.read_text(encoding="utf-8"))
        restored = decrypt_secret_bundle(saved, "FAKE_PASSPHRASE_123")
        assert restored["visual_crossing_api_key"] == "FAKE_VC_KEY_TEST"
        assert restored["pirate_weather_api_key"] == "FAKE_PW_KEY_TEST"
        assert restored["openrouter_api_key"] == "FAKE_OR_KEY_TEST"

    def test_export_resolves_lazy_secure_storage_values(self, tmp_path):
        """Export resolves LazySecureStorage objects via str()."""
        from accessiweather.config.secure_storage import LazySecureStorage

        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        config = MagicMock()
        # Simulate a LazySecureStorage value on one key
        lazy = LazySecureStorage("visual_crossing_api_key")
        lazy._value = "FAKE_VC_LAZY_TEST"
        lazy._loaded = True
        config.settings.visual_crossing_api_key = lazy
        config.settings.pirate_weather_api_key = "FAKE_PW_PLAIN_TEST"
        config.settings.openrouter_api_key = "FAKE_OR_PLAIN_TEST"
        manager._config = config
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"

        with patch(
            "accessiweather.config.import_export.SecureStorage.get_password",
            lambda _key_name: None,
        ):
            assert operations.export_encrypted_api_keys(export_file, "FAKE_PASSPHRASE_123") is True

        saved = json.loads(export_file.read_text(encoding="utf-8"))
        restored = decrypt_secret_bundle(saved, "FAKE_PASSPHRASE_123")
        assert restored["visual_crossing_api_key"] == "FAKE_VC_LAZY_TEST"
        assert restored["pirate_weather_api_key"] == "FAKE_PW_PLAIN_TEST"
        assert restored["openrouter_api_key"] == "FAKE_OR_PLAIN_TEST"

    def test_import_writes_all_keys_even_if_first_fails(self, tmp_path):
        """Import continues writing remaining keys after a failure."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        manager.app = None
        operations = ImportExportOperations(manager)

        secrets = {
            "visual_crossing_api_key": "FAKE_VC_VAL_TEST",
            "pirate_weather_api_key": "FAKE_PW_VAL_TEST",
            "openrouter_api_key": "FAKE_OR_VAL_TEST",
        }
        envelope = encrypt_secret_bundle(secrets, "FAKE_TEST_PASSPHRASE")
        export_file = tmp_path / "keys.keys"
        export_file.write_text(json.dumps(envelope), encoding="utf-8")

        written: dict[str, str] = {}

        def _set_pw(key_name: str, value: str) -> bool:
            if key_name == "visual_crossing_api_key":
                return False  # first key fails
            written[key_name] = value
            return True

        with patch("accessiweather.config.import_export.SecureStorage.set_password", _set_pw):
            result = operations.import_encrypted_api_keys(export_file, "FAKE_TEST_PASSPHRASE")

        # Returns False because one key failed
        assert result is False
        # But the second key was still written
        assert written["pirate_weather_api_key"] == "FAKE_PW_VAL_TEST"
        assert written["openrouter_api_key"] == "FAKE_OR_VAL_TEST"

    def test_import_sets_in_memory_keys_in_portable_mode(self, tmp_path):
        """In portable mode, import sets keys on settings directly."""
        from accessiweather.models import AppConfig

        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        app_mock = MagicMock()
        app_mock._portable_mode = True
        manager.app = app_mock
        config = AppConfig.default()
        manager._config = config
        operations = ImportExportOperations(manager)

        secrets = {
            "visual_crossing_api_key": "FAKE_VC_PORTABLE_TEST",
            "pirate_weather_api_key": "FAKE_PW_PORTABLE_TEST",
            "openrouter_api_key": "FAKE_OR_PORTABLE_TEST",
        }
        envelope = encrypt_secret_bundle(secrets, "FAKE_TEST_PASSPHRASE")
        export_file = tmp_path / "keys.keys"
        export_file.write_text(json.dumps(envelope), encoding="utf-8")

        with patch(
            "accessiweather.config.import_export.SecureStorage.set_password",
            lambda _k, _v: True,
        ):
            result = operations.import_encrypted_api_keys(export_file, "FAKE_TEST_PASSPHRASE")

        assert result is True
        assert config.settings.visual_crossing_api_key == "FAKE_VC_PORTABLE_TEST"
        assert config.settings.pirate_weather_api_key == "FAKE_PW_PORTABLE_TEST"
        assert config.settings.openrouter_api_key == "FAKE_OR_PORTABLE_TEST"
        # Should NOT call _load_secure_keys in portable mode
        manager._load_secure_keys.assert_not_called()

    def test_import_encrypted_api_keys_rejects_non_dict_bundle(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"
        export_file.write_text("[]", encoding="utf-8")

        with patch("accessiweather.config.import_export.SecureStorage.set_password") as mock_set:
            assert (
                operations.import_encrypted_api_keys(export_file, "FAKE_BUNDLE_PASSPHRASE") is False
            )
            mock_set.assert_not_called()

    def test_import_encrypted_api_keys_returns_false_when_no_supported_keys(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"
        envelope = encrypt_secret_bundle({"other": "value"}, "FAKE_RIGHT_PASS_TEST")
        export_file.write_text(json.dumps(envelope), encoding="utf-8")

        with patch("accessiweather.config.import_export.SecureStorage.set_password") as mock_set:
            assert (
                operations.import_encrypted_api_keys(export_file, "FAKE_RIGHT_PASS_TEST") is False
            )
            mock_set.assert_not_called()

    def test_import_encrypted_api_keys_wrong_passphrase_returns_false(self, tmp_path):
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        operations = ImportExportOperations(manager)

        export_file = tmp_path / "keys.keys"
        envelope = encrypt_secret_bundle(
            {"openrouter_api_key": "FAKE_OR_EXPORTED_TEST"}, "FAKE_RIGHT_PASS_TEST"
        )
        export_file.write_text(json.dumps(envelope), encoding="utf-8")

        with patch("accessiweather.config.import_export.SecureStorage.set_password") as mock_set:
            assert (
                operations.import_encrypted_api_keys(export_file, "FAKE_WRONG_PASS_TEST") is False
            )
            mock_set.assert_not_called()
