"""Platform detection module for AccessiWeather update system.

This module provides functionality to detect the current platform, deployment type,
and determine appropriate update artifacts for Briefcase-packaged applications.
"""

import logging
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PlatformInfo:
    """Information about the current platform and deployment."""

    platform: str  # 'windows', 'macos', 'linux'
    architecture: str  # 'x86_64', 'arm64', etc.
    deployment_type: str  # 'portable', 'installed'
    app_directory: Path  # Directory where the app is running from
    is_briefcase_app: bool  # Whether this is a Briefcase-packaged app
    update_capable: bool  # Whether auto-updates are possible


class PlatformDetector:
    """Detects platform information and deployment characteristics."""

    def __init__(self):
        """Initialize the platform detector."""
        self._platform_info: PlatformInfo | None = None

    def get_platform_info(self) -> PlatformInfo:
        """Get comprehensive platform information.

        Returns:
            PlatformInfo object with platform details

        """
        if self._platform_info is None:
            self._platform_info = self._detect_platform_info()
        return self._platform_info

    def _detect_platform_info(self) -> PlatformInfo:
        """Detect platform information."""
        # Detect basic platform
        system = platform.system().lower()
        platform_name = self._normalize_platform_name(system)

        # Detect architecture
        architecture = self._detect_architecture()

        # Detect deployment type and app directory
        app_directory = self._get_app_directory()
        deployment_type = self._detect_deployment_type(app_directory)

        # Check if this is a Briefcase app
        is_briefcase_app = self._is_briefcase_app(app_directory)

        # Determine if updates are possible
        update_capable = self._is_update_capable(deployment_type, app_directory)

        platform_info = PlatformInfo(
            platform=platform_name,
            architecture=architecture,
            deployment_type=deployment_type,
            app_directory=app_directory,
            is_briefcase_app=is_briefcase_app,
            update_capable=update_capable,
        )

        logger.info(f"Detected platform: {platform_info}")
        return platform_info

    def _normalize_platform_name(self, system: str) -> str:
        """Normalize platform name to standard format."""
        if system == "windows":
            return "windows"
        if system == "darwin":
            return "macos"
        if system == "linux":
            return "linux"
        logger.warning(f"Unknown platform: {system}, defaulting to linux")
        return "linux"

    def _detect_architecture(self) -> str:
        """Detect system architecture."""
        machine = platform.machine().lower()

        # Normalize architecture names
        if machine in ("x86_64", "amd64"):
            return "x86_64"
        if machine in ("arm64", "aarch64"):
            return "arm64"
        if machine in ("i386", "i686", "x86"):
            return "x86"
        logger.warning(f"Unknown architecture: {machine}, defaulting to x86_64")
        return "x86_64"

    def _get_app_directory(self) -> Path:
        """Get the directory where the application is running from."""
        if getattr(sys, "frozen", False):
            # Running as a packaged executable
            if hasattr(sys, "_MEIPASS"):
                # PyInstaller
                return Path(sys.executable).parent
            # Other packagers (including Briefcase)
            return Path(sys.executable).parent
        # Running from source
        return Path(__file__).parent.parent.parent.parent

    def _detect_deployment_type(self, app_directory: Path) -> str:
        """Detect whether the app is portable or installed.

        Args:
            app_directory: Directory where the app is running from

        Returns:
            'portable' or 'installed'

        """
        app_dir_str = str(app_directory).lower()

        # Check for typical installation paths
        installation_paths = {
            "windows": [
                "program files",
                "program files (x86)",
                r"c:\program files",
                r"c:\program files (x86)",
            ],
            "macos": [
                "/applications",
                "/system/applications",
                "/usr/local",
            ],
            "linux": [
                "/usr/bin",
                "/usr/local/bin",
                "/opt",
                "/snap",
                "/flatpak",
            ],
        }

        platform_name = self._normalize_platform_name(platform.system().lower())
        paths_to_check = installation_paths.get(platform_name, [])

        for install_path in paths_to_check:
            if install_path in app_dir_str:
                return "installed"

        # If not in typical installation paths, assume portable
        return "portable"

    def _is_briefcase_app(self, app_directory: Path) -> bool:
        """Check if this is a Briefcase-packaged application.

        Args:
            app_directory: Directory where the app is running from

        Returns:
            True if this appears to be a Briefcase app

        """
        # Look for Briefcase-specific indicators
        briefcase_indicators = [
            "app_packages",  # Briefcase creates this directory
            "support",  # Briefcase support files
        ]

        for indicator in briefcase_indicators:
            if (app_directory / indicator).exists():
                return True

        # Check for Briefcase metadata
        metadata_files = [
            "briefcase.toml",
            "pyproject.toml",
        ]

        for metadata_file in metadata_files:
            metadata_path = app_directory / metadata_file
            if metadata_path.exists():
                try:
                    content = metadata_path.read_text()
                    if "briefcase" in content.lower():
                        return True
                except Exception:
                    pass

        return False

    def _is_update_capable(self, deployment_type: str, app_directory: Path) -> bool:
        """Determine if the app can perform auto-updates.

        Args:
            deployment_type: 'portable' or 'installed'
            app_directory: Directory where the app is running from

        Returns:
            True if auto-updates are possible

        """
        # Portable apps are generally update-capable
        if deployment_type == "portable":
            # Check if we have write permissions to the app directory
            try:
                test_file = app_directory / ".update_test"
                test_file.touch()
                test_file.unlink()
                return True
            except (PermissionError, OSError):
                logger.warning("No write permission to app directory, updates not possible")
                return False

        # Installed apps typically require elevated permissions for updates
        # We'll handle these with manual update notifications
        return False

    def get_update_artifacts(self, version: str) -> dict[str, str]:
        """Get the appropriate update artifacts for the current platform.

        Args:
            version: Version string (e.g., "1.0.0")

        Returns:
            Dictionary mapping artifact types to filenames

        """
        platform_info = self.get_platform_info()

        artifacts = {
            "windows": {
                "installer": f"AccessiWeather_Setup_v{version}.msi",
                "portable": f"AccessiWeather_Portable_v{version}.zip",
            },
            "macos": {
                "installer": f"AccessiWeather_v{version}.dmg",
                "portable": f"AccessiWeather_Portable_v{version}.zip",
            },
            "linux": {
                "installer": f"AccessiWeather_v{version}.deb",
                "portable": f"AccessiWeather_v{version}.AppImage",
            },
        }

        return artifacts.get(platform_info.platform, artifacts["linux"])

    def is_portable(self) -> bool:
        """Check if the current deployment is portable.

        Returns:
            True if running from a portable deployment

        """
        return self.get_platform_info().deployment_type == "portable"

    def is_update_capable(self) -> bool:
        """Check if auto-updates are possible.

        Returns:
            True if auto-updates are possible

        """
        return self.get_platform_info().update_capable
