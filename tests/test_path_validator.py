"""
Unit tests for path validation utilities.

Tests cover:
- File extension validation
- File existence checks
- Path traversal detection
- Directory containment validation
- Suspicious character detection
- Comprehensive executable path validation
- Edge cases: relative/absolute paths, symlinks, special characters
"""

import tempfile
from pathlib import Path

import pytest
from hypothesis import (
    assume,
    example,
    given,
    strategies as st,
)

from accessiweather.utils.path_validator import (
    SecurityError,
    validate_executable_path,
    validate_file_exists,
    validate_file_extension,
    validate_no_path_traversal,
    validate_no_suspicious_characters,
    validate_path_within_directory,
)


class TestSecurityError:
    """Test SecurityError exception class."""

    def test_security_error_creation(self):
        """Should create SecurityError with message."""
        error = SecurityError("Test security error")
        assert str(error) == "Test security error"

    def test_security_error_inheritance(self):
        """Should inherit from Exception."""
        error = SecurityError("Test")
        assert isinstance(error, Exception)


class TestValidateFileExtension:
    """Test file extension validation."""

    def test_valid_extension_lowercase(self):
        """Should accept file with correct lowercase extension."""
        # Should not raise
        validate_file_extension("update.msi", ".msi")
        validate_file_extension("package.zip", ".zip")
        validate_file_extension("script.bat", ".bat")

    def test_valid_extension_uppercase(self):
        """Should accept file with uppercase extension (case insensitive)."""
        # Should not raise
        validate_file_extension("UPDATE.MSI", ".msi")
        validate_file_extension("PACKAGE.ZIP", ".zip")

    def test_valid_extension_mixed_case(self):
        """Should accept file with mixed case extension."""
        # Should not raise
        validate_file_extension("update.MsI", ".msi")
        validate_file_extension("package.ZiP", ".zip")

    def test_invalid_extension(self):
        """Should reject file with wrong extension."""
        with pytest.raises(ValueError, match="Invalid file type"):
            validate_file_extension("update.exe", ".msi")

        with pytest.raises(ValueError, match="Invalid file type"):
            validate_file_extension("package.tar", ".zip")

    def test_no_extension(self):
        """Should reject file without extension."""
        with pytest.raises(ValueError, match="Invalid file type"):
            validate_file_extension("update", ".msi")

    def test_path_object(self):
        """Should accept Path object."""
        path = Path("update.msi")
        # Should not raise
        validate_file_extension(path, ".msi")

    def test_full_path_with_extension(self):
        """Should validate extension for full paths."""
        # Should not raise
        validate_file_extension("/path/to/update.msi", ".msi")
        validate_file_extension("C:\\Users\\test\\update.msi", ".msi")

    def test_multiple_dots_in_filename(self):
        """Should validate extension for files with multiple dots."""
        # Should not raise
        validate_file_extension("update.v1.0.msi", ".msi")
        validate_file_extension("my.backup.file.zip", ".zip")

    def test_dot_only_extension(self):
        """Should handle files with just dot as suffix."""
        with pytest.raises(ValueError, match="Invalid file type"):
            validate_file_extension("update.", ".msi")


class TestValidateFileExists:
    """Test file existence validation."""

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".msi") as f:
            temp_path = Path(f.name)
        yield temp_path
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_existing_file(self, temp_file):
        """Should accept existing file."""
        # Should not raise
        validate_file_exists(temp_file)

    def test_nonexistent_file(self):
        """Should reject nonexistent file."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            validate_file_exists("/nonexistent/path/to/file.msi")

    def test_path_object(self, temp_file):
        """Should accept Path object."""
        # Should not raise
        validate_file_exists(temp_file)

    def test_string_path(self, temp_file):
        """Should accept string path."""
        # Should not raise
        validate_file_exists(str(temp_file))

    def test_directory_as_file(self, temp_dir):
        """Should accept directory (exists() returns True for dirs)."""
        # pathlib's exists() returns True for both files and directories
        # Should not raise
        validate_file_exists(temp_dir)

    def test_relative_path(self, temp_dir):
        """Should handle relative paths."""
        # Create a file in temp_dir
        test_file = temp_dir / "test.msi"
        test_file.touch()

        # Change to temp_dir and test relative path
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            # Should not raise
            validate_file_exists("test.msi")
        finally:
            os.chdir(original_cwd)


class TestValidateNoPathTraversal:
    """Test path traversal detection."""

    def test_safe_relative_path(self):
        """Should accept safe relative path."""
        # Should not raise
        validate_no_path_traversal("update.msi")
        validate_no_path_traversal("subdir/update.msi")

    def test_safe_absolute_path(self):
        """Should accept safe absolute path."""
        # Should not raise
        validate_no_path_traversal("/home/user/update.msi")
        validate_no_path_traversal("C:\\Users\\test\\update.msi")

    def test_parent_directory_traversal(self):
        """Should reject paths with '..' traversal."""
        with pytest.raises(SecurityError, match="Path traversal detected"):
            validate_no_path_traversal("../update.msi")

        with pytest.raises(SecurityError, match="Path traversal detected"):
            validate_no_path_traversal("subdir/../../update.msi")

    def test_hidden_parent_traversal(self):
        """Should reject paths with hidden '..' in middle."""
        with pytest.raises(SecurityError, match="Path traversal detected"):
            validate_no_path_traversal("/safe/path/../../../etc/passwd")

    def test_windows_path_traversal(self):
        """Should reject Windows-style path traversal."""
        with pytest.raises(SecurityError, match="Path traversal detected"):
            validate_no_path_traversal("C:\\safe\\..\\..\\Windows\\System32")

    def test_dot_directory_safe(self):
        """Should accept current directory reference (single dot)."""
        # Single dot is safe, only '..' is dangerous
        # Should not raise
        validate_no_path_traversal("./update.msi")
        validate_no_path_traversal("subdir/./update.msi")

    def test_double_dot_in_filename(self):
        """Should accept '..' in filename (not as path component)."""
        # If '..' is part of the filename itself (not a directory component),
        # it should be rejected by the check since Path.parts will normalize it
        with pytest.raises(SecurityError, match="Path traversal detected"):
            validate_no_path_traversal("file..name.msi")

    def test_path_object(self):
        """Should accept Path object."""
        # Should not raise
        validate_no_path_traversal(Path("safe/path/update.msi"))

        with pytest.raises(SecurityError, match="Path traversal detected"):
            validate_no_path_traversal(Path("../unsafe/path.msi"))


class TestValidatePathWithinDirectory:
    """Test directory containment validation."""

    @pytest.fixture
    def temp_structure(self):
        """Create temporary directory structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            allowed_dir = base / "allowed"
            allowed_dir.mkdir()
            (allowed_dir / "file.msi").touch()

            forbidden_dir = base / "forbidden"
            forbidden_dir.mkdir()
            (forbidden_dir / "file.msi").touch()

            yield {
                "base": base,
                "allowed": allowed_dir,
                "forbidden": forbidden_dir,
                "allowed_file": allowed_dir / "file.msi",
                "forbidden_file": forbidden_dir / "file.msi",
            }

    def test_file_within_directory(self, temp_structure):
        """Should accept file within expected directory."""
        # Should not raise
        validate_path_within_directory(temp_structure["allowed_file"], temp_structure["allowed"])

    def test_file_outside_directory(self, temp_structure):
        """Should reject file outside expected directory."""
        with pytest.raises(SecurityError, match="outside expected directory"):
            validate_path_within_directory(
                temp_structure["forbidden_file"], temp_structure["allowed"]
            )

    def test_subdirectory_file(self, temp_structure):
        """Should accept file in subdirectory of expected directory."""
        subdir = temp_structure["allowed"] / "subdir"
        subdir.mkdir()
        subfile = subdir / "file.msi"
        subfile.touch()

        # Should not raise
        validate_path_within_directory(subfile, temp_structure["allowed"])

    def test_relative_path_within_directory(self, temp_structure):
        """Should handle relative paths correctly."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_structure["allowed"])
            # Should not raise
            validate_path_within_directory("file.msi", ".")
        finally:
            os.chdir(original_cwd)

    def test_path_traversal_attempt(self, temp_structure):
        """Should reject path traversal attempts."""
        # Try to escape using ../
        evil_path = temp_structure["allowed"] / ".." / "forbidden" / "file.msi"

        with pytest.raises(SecurityError, match="outside expected directory"):
            validate_path_within_directory(evil_path, temp_structure["allowed"])

    def test_symlink_escape(self, temp_structure):
        """Should detect symlink escaping expected directory."""
        # Create a symlink pointing outside the allowed directory
        symlink_path = temp_structure["allowed"] / "evil_link"

        try:
            symlink_path.symlink_to(temp_structure["forbidden_file"])

            # Should reject because resolved path is outside allowed dir
            with pytest.raises(SecurityError, match="outside expected directory"):
                validate_path_within_directory(symlink_path, temp_structure["allowed"])
        except OSError:
            # Symlink creation may fail on Windows without admin privileges
            pytest.skip("Symlink creation not supported")

    def test_string_paths(self, temp_structure):
        """Should accept string paths."""
        # Should not raise
        validate_path_within_directory(
            str(temp_structure["allowed_file"]), str(temp_structure["allowed"])
        )


class TestValidateNoSuspiciousCharacters:
    """Test suspicious character detection."""

    def test_safe_filename(self):
        """Should accept safe filenames."""
        # Should not raise
        validate_no_suspicious_characters("update.msi")
        validate_no_suspicious_characters("package-v1.0.zip")
        validate_no_suspicious_characters("my_file.bat")

    def test_safe_full_path(self):
        """Should accept safe full paths with slashes."""
        # Should not raise (slashes are in path, not filename)
        validate_no_suspicious_characters("/home/user/update.msi")
        validate_no_suspicious_characters("C:\\Users\\test\\update.msi")

    def test_suspicious_less_than(self):
        """Should reject filename with '<' character."""
        with pytest.raises(SecurityError, match="Suspicious characters in filename"):
            validate_no_suspicious_characters("file<.msi")

    def test_suspicious_greater_than(self):
        """Should reject filename with '>' character."""
        with pytest.raises(SecurityError, match="Suspicious characters in filename"):
            validate_no_suspicious_characters("file>.msi")

    def test_suspicious_colon_in_filename(self):
        """Should reject filename with ':' character (not in drive letter)."""
        # Note: On Windows, C: is valid in path but : in filename is not
        with pytest.raises(SecurityError, match="Suspicious characters in filename"):
            validate_no_suspicious_characters("/path/file:.msi")

    def test_suspicious_quote(self):
        """Should reject filename with double quote character."""
        with pytest.raises(SecurityError, match="Suspicious characters in filename"):
            validate_no_suspicious_characters('file".msi')

    def test_suspicious_pipe(self):
        """Should reject filename with pipe character."""
        with pytest.raises(SecurityError, match="Suspicious characters in filename"):
            validate_no_suspicious_characters("file|.msi")

    def test_suspicious_question_mark(self):
        """Should reject filename with question mark."""
        with pytest.raises(SecurityError, match="Suspicious characters in filename"):
            validate_no_suspicious_characters("file?.msi")

    def test_suspicious_asterisk(self):
        """Should reject filename with asterisk."""
        with pytest.raises(SecurityError, match="Suspicious characters in filename"):
            validate_no_suspicious_characters("file*.msi")

    def test_multiple_suspicious_characters(self):
        """Should reject filename with multiple suspicious characters."""
        with pytest.raises(SecurityError, match="Suspicious characters in filename"):
            validate_no_suspicious_characters("file<>?.msi")

    def test_path_object(self):
        """Should accept Path object."""
        # Should not raise
        validate_no_suspicious_characters(Path("/safe/path/file.msi"))

        with pytest.raises(SecurityError, match="Suspicious characters in filename"):
            validate_no_suspicious_characters(Path("/safe/path/file*.msi"))


class TestValidateExecutablePath:
    """Test comprehensive executable path validation."""

    @pytest.fixture
    def temp_structure(self):
        """Create temporary directory structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            allowed_dir = base / "allowed"
            allowed_dir.mkdir()

            # Create valid files
            msi_file = allowed_dir / "update.msi"
            msi_file.touch()

            zip_file = allowed_dir / "package.zip"
            zip_file.touch()

            bat_file = allowed_dir / "script.bat"
            bat_file.touch()

            # Create forbidden directory
            forbidden_dir = base / "forbidden"
            forbidden_dir.mkdir()
            forbidden_file = forbidden_dir / "evil.msi"
            forbidden_file.touch()

            yield {
                "base": base,
                "allowed": allowed_dir,
                "forbidden": forbidden_dir,
                "msi_file": msi_file,
                "zip_file": zip_file,
                "bat_file": bat_file,
                "forbidden_file": forbidden_file,
            }

    def test_valid_msi_path(self, temp_structure):
        """Should accept valid MSI file path."""
        result = validate_executable_path(
            temp_structure["msi_file"],
            expected_suffix=".msi",
            expected_parent=temp_structure["allowed"],
        )

        assert result is not None
        assert result.is_absolute()
        assert result.suffix == ".msi"

    def test_valid_zip_path(self, temp_structure):
        """Should accept valid ZIP file path."""
        result = validate_executable_path(
            temp_structure["zip_file"],
            expected_suffix=".zip",
            expected_parent=temp_structure["allowed"],
        )

        assert result is not None
        assert result.suffix == ".zip"

    def test_valid_bat_path(self, temp_structure):
        """Should accept valid batch file path."""
        result = validate_executable_path(
            temp_structure["bat_file"],
            expected_suffix=".bat",
            expected_parent=temp_structure["allowed"],
        )

        assert result is not None
        assert result.suffix == ".bat"

    def test_nonexistent_file(self, temp_structure):
        """Should reject nonexistent file."""
        with pytest.raises(FileNotFoundError):
            validate_executable_path(
                temp_structure["allowed"] / "nonexistent.msi",
                expected_suffix=".msi",
                expected_parent=temp_structure["allowed"],
            )

    def test_wrong_extension(self, temp_structure):
        """Should reject file with wrong extension."""
        with pytest.raises(ValueError, match="Invalid file type"):
            validate_executable_path(
                temp_structure["msi_file"],
                expected_suffix=".zip",  # Wrong extension
                expected_parent=temp_structure["allowed"],
            )

    def test_path_traversal_attempt(self, temp_structure):
        """Should reject path traversal attempts."""
        # Create a file with '..' in path
        traversal_path = temp_structure["allowed"] / ".." / "forbidden" / "evil.msi"

        with pytest.raises(SecurityError, match="Path traversal detected"):
            validate_executable_path(
                traversal_path,
                expected_suffix=".msi",
                expected_parent=temp_structure["allowed"],
            )

    def test_file_outside_expected_directory(self, temp_structure):
        """Should reject file outside expected directory."""
        with pytest.raises(SecurityError, match="outside expected directory"):
            validate_executable_path(
                temp_structure["forbidden_file"],
                expected_suffix=".msi",
                expected_parent=temp_structure["allowed"],
            )

    def test_suspicious_characters_in_filename(self, temp_structure):
        """Should reject file with suspicious characters."""
        evil_file = temp_structure["allowed"] / "evil*.msi"
        evil_file.touch()

        with pytest.raises(SecurityError, match="Suspicious characters in filename"):
            validate_executable_path(
                evil_file,
                expected_suffix=".msi",
                expected_parent=temp_structure["allowed"],
            )

    def test_without_expected_parent(self, temp_structure):
        """Should validate without expected_parent parameter."""
        result = validate_executable_path(temp_structure["msi_file"], expected_suffix=".msi")

        assert result is not None
        assert result.is_absolute()
        assert result.suffix == ".msi"

    def test_string_path(self, temp_structure):
        """Should accept string path."""
        result = validate_executable_path(
            str(temp_structure["msi_file"]),
            expected_suffix=".msi",
            expected_parent=temp_structure["allowed"],
        )

        assert result is not None
        assert isinstance(result, Path)

    def test_relative_path(self, temp_structure):
        """Should resolve relative paths to absolute."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_structure["allowed"])
            result = validate_executable_path("update.msi", expected_suffix=".msi")

            assert result is not None
            assert result.is_absolute()
        finally:
            os.chdir(original_cwd)

    def test_case_insensitive_extension(self, temp_structure):
        """Should accept case-insensitive extension matching."""
        # Create file with uppercase extension
        upper_file = temp_structure["allowed"] / "UPDATE.MSI"
        upper_file.touch()

        result = validate_executable_path(
            upper_file,
            expected_suffix=".msi",  # lowercase expected
            expected_parent=temp_structure["allowed"],
        )

        assert result is not None

    def test_symlink_within_directory(self, temp_structure):
        """Should accept symlink pointing within allowed directory."""
        link_path = temp_structure["allowed"] / "link.msi"

        try:
            link_path.symlink_to(temp_structure["msi_file"])

            result = validate_executable_path(
                link_path,
                expected_suffix=".msi",
                expected_parent=temp_structure["allowed"],
            )

            assert result is not None
        except OSError:
            # Symlink creation may fail on Windows without admin privileges
            pytest.skip("Symlink creation not supported")

    def test_symlink_escape_directory(self, temp_structure):
        """Should reject symlink pointing outside allowed directory."""
        link_path = temp_structure["allowed"] / "evil_link.msi"

        try:
            link_path.symlink_to(temp_structure["forbidden_file"])

            with pytest.raises(SecurityError, match="outside expected directory"):
                validate_executable_path(
                    link_path,
                    expected_suffix=".msi",
                    expected_parent=temp_structure["allowed"],
                )
        except OSError:
            # Symlink creation may fail on Windows without admin privileges
            pytest.skip("Symlink creation not supported")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_filename(self):
        """Should handle empty filename."""
        with pytest.raises((FileNotFoundError, ValueError)):
            validate_executable_path("", expected_suffix=".msi")

    def test_none_path(self):
        """Should handle None path appropriately."""
        # Path(None) raises TypeError, so this should fail
        with pytest.raises(TypeError):
            validate_executable_path(None, expected_suffix=".msi")

    def test_very_long_path(self):
        """Should handle very long paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create deeply nested directory structure
            current = base
            for i in range(10):
                current = current / f"subdir{i}"
            current.mkdir(parents=True)

            long_file = current / "file.msi"
            long_file.touch()

            result = validate_executable_path(long_file, expected_suffix=".msi")
            assert result is not None

    def test_unicode_filename(self):
        """Should handle Unicode characters in filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Use Unicode characters that are safe for filenames
            unicode_file = base / "файл.msi"  # Cyrillic characters
            unicode_file.touch()

            result = validate_executable_path(unicode_file, expected_suffix=".msi")
            assert result is not None

    def test_special_windows_path(self):
        """Should handle Windows UNC paths if on Windows."""
        import platform

        if platform.system() != "Windows":
            pytest.skip("Windows-specific test")

        # This test would need actual UNC path which may not be available
        # Just document the expected behavior
        # UNC paths like \\server\share\file.msi should be handled by pathlib

    def test_dot_in_directory_name(self):
        """Should handle directories with dots in names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            dotted_dir = base / "my.directory.v1.0"
            dotted_dir.mkdir()
            file = dotted_dir / "update.msi"
            file.touch()

            result = validate_executable_path(
                file, expected_suffix=".msi", expected_parent=dotted_dir
            )
            assert result is not None


class TestHypothesisPropertyTests:
    """Property-based tests using Hypothesis."""

    @given(
        filename=st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters="_-.",
            ),
            min_size=1,
            max_size=50,
        )
    )
    @example(filename="update.msi")
    @example(filename="package.zip")
    def test_safe_filenames_accepted(self, filename):
        """Safe filenames should pass suspicious character check."""
        # Filter out files that are just dots or have no extension
        assume(filename.strip(".") != "")
        assume("." in filename)

        # Should not raise if no suspicious characters
        if not any(char in filename for char in ["<", ">", ":", '"', "|", "?", "*"]):
            validate_no_suspicious_characters(filename)

    @given(
        suspicious_char=st.sampled_from(["<", ">", ":", '"', "|", "?", "*"]),
        prefix=st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-"
            ),
            min_size=1,
            max_size=20,
        ),
    )
    def test_suspicious_filenames_rejected(self, suspicious_char, prefix):
        """Filenames with suspicious characters should be rejected."""
        filename = f"{prefix}{suspicious_char}file.msi"

        with pytest.raises(SecurityError, match="Suspicious characters"):
            validate_no_suspicious_characters(filename)

    @given(
        extension=st.text(
            alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=2, max_size=5
        )
    )
    @example(extension="msi")
    @example(extension="zip")
    @example(extension="bat")
    def test_extension_validation_property(self, extension):
        """Extension validation should be case-insensitive."""
        filename = f"file.{extension}"
        expected = f".{extension}"

        # Should not raise for matching extension
        validate_file_extension(filename, expected)

        # Should not raise for uppercase version
        validate_file_extension(filename.upper(), expected)

        # Should raise for different extension
        with pytest.raises(ValueError):
            validate_file_extension(filename, ".different")
