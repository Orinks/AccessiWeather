"""TUF-enabled update service for AccessiWeather.

This module provides secure update functionality using The Update Framework (TUF)
with fallback to GitHub releases for development and testing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from accessiweather.version import __version__

logger = logging.getLogger(__name__)

# Try to import TUF components
try:
    import tufup
    from tufup.client import Client as TUFClient

    TUF_AVAILABLE = True
    tufup_version = getattr(tufup, "__version__", "unknown")
    logger.info(f"TUF (tufup) is available - version: {tufup_version}")
except ImportError as e:
    TUF_AVAILABLE = False
    logger.warning(
        f"TUF (tufup) not available - falling back to GitHub releases. "
        f"Install with: pip install tufup. Error: {e}"
    )
    logger.debug(f"Full TUF import error traceback:", exc_info=True)


@dataclass
class UpdateInfo:
    """Information about an available update."""

    version: str
    download_url: str
    artifact_name: str
    release_notes: str
    is_prerelease: bool = False
    file_size: int | None = None
    checksum: str | None = None


@dataclass
class UpdateSettings:
    """Update service settings."""

    method: str = "github"  # "tuf" or "github"
    channel: str = "stable"  # "stable" or "dev"
    auto_check: bool = True
    check_interval_hours: int = 24
    repo_owner: str = "joshuakitchen"
    repo_name: str = "accessiweather"
    tuf_repo_url: str = "https://updates.accessiweather.app"


class TUFUpdateService:
    """Simple, clean update service with TUF support."""

    def __init__(self, app_name: str = "AccessiWeather", config_dir: Path | None = None):
        """Initialize the update service.

        Args:
            app_name: Name of the application
            config_dir: Directory for storing update configuration

        """
        self.app_name = app_name
        self.config_dir = config_dir or Path.home() / f".{app_name.lower()}"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Settings file
        self.settings_file = self.config_dir / "update_settings.json"
        self.settings = self._load_settings()

        # TUF client (initialized on demand)
        self._tuf_client: TUFClient | None = None
        self._tuf_initialized = False

        # HTTP client for GitHub API
        self._http_client = httpx.AsyncClient(
            timeout=30.0, headers={"User-Agent": f"{app_name}/1.0"}
        )

        logger.info(f"Update service initialized for {app_name}")
        logger.info(f"TUF available: {TUF_AVAILABLE}")
        logger.info(f"Current method: {self.settings.method}")

    @property
    def tuf_available(self) -> bool:
        """Check if TUF is available."""
        return TUF_AVAILABLE

    @property
    def current_method(self) -> str:
        """Get the current update method."""
        return self.settings.method

    def _load_settings(self) -> UpdateSettings:
        """Load settings from file or create defaults."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file) as f:
                    data = json.load(f)
                    return UpdateSettings(**data)
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")

        # Return defaults
        settings = UpdateSettings()
        # Use TUF if available, otherwise GitHub
        if TUF_AVAILABLE:
            settings.method = "tuf"

        self._save_settings(settings)
        return settings

    def _save_settings(self, settings: UpdateSettings) -> None:
        """Save settings to file."""
        try:
            with open(self.settings_file, "w") as f:
                json.dump(settings.__dict__, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def update_settings(self, **kwargs) -> None:
        """Update settings."""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)

        self._save_settings(self.settings)
        logger.info(f"Settings updated: {kwargs}")

    def get_settings_dict(self) -> dict[str, Any]:
        """Get settings as dictionary."""
        return {
            "method": self.settings.method,
            "channel": self.settings.channel,
            "auto_check": self.settings.auto_check,
            "check_interval_hours": self.settings.check_interval_hours,
            "tuf_available": TUF_AVAILABLE,
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "python_version": platform.python_version(),
            },
        }

    async def check_for_updates(self, method: str | None = None) -> UpdateInfo | None:
        """Check for available updates.

        Args:
            method: Update method to use ("tuf", "github", or "auto"). Uses settings default if None.

        Returns:
            UpdateInfo if update available, None otherwise

        """
        check_method = method or self.settings.method

        logger.info(f"Checking for updates using method: {check_method}")

        try:
            if check_method == "auto":
                # Auto method: use TUF for stable, GitHub for beta/dev
                if self.settings.channel == "stable" and TUF_AVAILABLE:
                    logger.info("Auto method: using TUF for stable channel")
                    return await self._check_tuf_updates()
                logger.info(f"Auto method: using GitHub for {self.settings.channel} channel")
                return await self._check_github_updates()
            if check_method == "tuf" and TUF_AVAILABLE:
                return await self._check_tuf_updates()
            return await self._check_github_updates()
        except Exception as e:
            logger.error(f"Update check failed: {e}")
            return None

    async def _check_tuf_updates(self) -> UpdateInfo | None:
        """Check for updates using TUF."""
        if not TUF_AVAILABLE:
            logger.warning("TUF not available")
            return None

        try:
            # Initialize TUF client if needed
            if not self._tuf_initialized:
                await self._init_tuf_client()

            if not self._tuf_client:
                logger.warning("TUF client not initialized")
                return None

            # Check for updates using TUF client
            logger.info("Checking TUF repository for updates...")

            # Use the tufup client to check for updates
            # The pre parameter can be used for pre-release channels (PEP 440 identifiers)
            if self.settings.channel == "stable":
                pre_release = None
            elif self.settings.channel == "beta":
                pre_release = "b"  # PEP 440 beta identifier
            elif self.settings.channel == "dev":
                pre_release = "a"  # PEP 440 alpha identifier
            elif self.settings.channel == "rc":
                pre_release = "rc"  # PEP 440 release candidate identifier
            else:
                pre_release = None

            new_update = self._tuf_client.check_for_updates(pre=pre_release)

            if new_update:
                logger.info(f"TUF update found: {new_update}")

                # Convert tufup update info to our UpdateInfo format
                return UpdateInfo(
                    version=str(new_update.version),
                    download_url="",  # TUF handles downloads internally
                    artifact_name=f"{self.app_name}-{new_update.version}.tar.gz",
                    release_notes=getattr(new_update, "custom", {}).get("release_notes", ""),
                    is_prerelease=(pre_release is not None),
                )
            logger.info("No TUF updates available")
            return None

        except Exception as e:
            logger.error(f"TUF update check failed: {e}")
            return None

    async def _check_github_updates(self) -> UpdateInfo | None:
        """Check for updates using GitHub releases."""
        try:
            url = f"https://api.github.com/repos/{self.settings.repo_owner}/{self.settings.repo_name}/releases"

            # Add channel filter
            if self.settings.channel == "stable":
                url += "?per_page=10"  # Get recent releases
            else:
                url += "?per_page=20"  # Include prereleases

            logger.info(f"Checking GitHub releases: {url}")

            response = await self._http_client.get(url)
            response.raise_for_status()

            releases = response.json()

            # Filter releases based on channel
            for release in releases:
                is_prerelease = release.get("prerelease", False)
                version = release["tag_name"].lstrip("v")

                # Channel-based filtering
                if self.settings.channel == "stable":
                    # Stable channel: only non-prerelease versions
                    if is_prerelease:
                        continue
                elif self.settings.channel == "beta":
                    # Beta channel: only beta/rc prereleases, no dev/alpha
                    if not is_prerelease:
                        continue  # Skip stable releases for beta channel
                    if not any(keyword in version.lower() for keyword in ["beta", "rc"]):
                        continue  # Skip non-beta prereleases
                elif self.settings.channel == "dev":
                    # Dev channel: all releases (stable and prerelease)
                    pass  # No filtering needed
                else:
                    # Unknown channel, default to stable behavior
                    if is_prerelease:
                        continue

                # Find appropriate asset for current platform
                asset = self._find_platform_asset(release.get("assets", []))
                if not asset:
                    continue

                return UpdateInfo(
                    version=version,
                    download_url=asset["browser_download_url"],
                    artifact_name=asset["name"],
                    release_notes=release.get("body", ""),
                    is_prerelease=is_prerelease,
                    file_size=asset.get("size"),
                )

            logger.info("No GitHub updates available")
            return None

        except Exception as e:
            logger.error(f"GitHub update check failed: {e}")
            return None

    def _find_platform_asset(self, assets: list) -> dict | None:
        """Find the appropriate asset for the current platform."""
        system = platform.system().lower()

        # Platform-specific patterns
        patterns = []
        if system == "windows":
            patterns = ["windows", "win", ".exe", ".msi"]
        elif system == "linux":
            patterns = ["linux", ".tar.gz", ".deb", ".rpm"]
        elif system == "darwin":
            patterns = ["macos", "darwin", ".dmg", ".pkg"]

        # Look for matching assets
        for asset in assets:
            name = asset["name"].lower()
            if any(pattern in name for pattern in patterns):
                return asset

        # Fallback to first asset
        return assets[0] if assets else None

    async def _init_tuf_client(self) -> bool:
        """Initialize TUF client with comprehensive validation."""
        if not TUF_AVAILABLE:
            logger.error("TUF not available - cannot initialize client")
            return False

        try:
            logger.info("Starting TUF client initialization...")

            # Perform pre-initialization validation
            validation_result = await self._validate_tuf_configuration()
            if not validation_result:
                logger.error("TUF configuration validation failed")
                return False

            logger.debug("TUF configuration validation passed")

            # Create TUF directories
            tuf_dir = self.config_dir / "tuf"
            metadata_dir = tuf_dir / "metadata"
            targets_dir = tuf_dir / "targets"

            try:
                metadata_dir.mkdir(parents=True, exist_ok=True)
                targets_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created TUF directories: {tuf_dir}")
            except PermissionError as e:
                logger.error(f"Permission denied creating TUF directories: {e}")
                return False
            except OSError as e:
                logger.error(f"OS error creating TUF directories: {e}")
                return False

            # Ensure root metadata exists and is valid
            root_path = metadata_dir / "root.json"
            if not root_path.exists():
                logger.info("Root metadata not found, attempting to copy from app bundle")
                if not self._copy_root_metadata(root_path):
                    logger.error(
                        "Could not find or copy valid root.json - TUF client cannot be initialized"
                    )
                    return False
            elif not self._validate_root_json(root_path):
                logger.warning("Existing root.json is invalid, attempting to replace")
                root_path.unlink(missing_ok=True)
                if not self._copy_root_metadata(root_path):
                    logger.error(
                        "Could not replace invalid root.json - TUF client cannot be initialized"
                    )
                    return False

            # Validate current version format
            if not self._validate_version_format(__version__):
                logger.error(f"Current version format is invalid: {__version__}")
                return False

            # Initialize TUF client with proper parameters
            try:
                self._tuf_client = TUFClient(
                    app_name=self.app_name,
                    app_install_dir=self.config_dir.parent
                    / "app",  # Where updates will be installed
                    current_version=__version__,  # Current app version from version.py
                    metadata_dir=metadata_dir,
                    metadata_base_url=self.settings.tuf_repo_url,
                    target_dir=targets_dir,
                    target_base_url=self.settings.tuf_repo_url,
                    refresh_required=False,
                )
                logger.debug("TUF client object created successfully")
            except Exception as e:
                logger.error(f"Failed to create TUF client object: {e}")
                logger.debug("TUF client creation error details:", exc_info=True)
                return False

            self._tuf_initialized = True
            logger.info("TUF client initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize TUF client: {e}")
            logger.debug("TUF client initialization error details:", exc_info=True)
            return False

    def _copy_root_metadata(self, dest_path: Path) -> bool:
        """Copy root.json from app bundle with comprehensive validation."""
        try:
            # Possible locations for root.json
            possible_locations = [
                Path(__file__).parent.parent / "resources" / "root.json",
                Path(__file__).parent.parent.parent.parent / "resources" / "root.json",
                Path(__file__).parent / "resources" / "root.json",
            ]

            for source_path in possible_locations:
                if source_path.exists():
                    logger.debug(f"Found root.json at {source_path}")

                    # Validate source file before copying
                    if not self._validate_root_json(source_path):
                        logger.error(f"Source root.json at {source_path} is invalid")
                        continue

                    import shutil

                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, dest_path)
                    logger.info(f"Copied root metadata from {source_path}")

                    # Validate copied file
                    if not self._validate_root_json(dest_path):
                        logger.error(f"Copied root.json at {dest_path} is invalid")
                        dest_path.unlink(missing_ok=True)
                        return False

                    logger.debug("Root metadata validation successful after copy")
                    return True

            logger.warning("Could not find valid root.json in app bundle")
            return False

        except Exception as e:
            logger.error(f"Failed to copy root metadata: {e}")
            logger.debug("Root metadata copy error details:", exc_info=True)
            return False

    def _validate_root_json(self, root_path: Path) -> bool:
        """Validate root.json file structure and content.

        Args:
            root_path: Path to the root.json file to validate

        Returns:
            bool: True if valid, False otherwise

        """
        try:
            if not root_path.exists():
                logger.error(f"Root metadata file does not exist: {root_path}")
                return False

            if not root_path.is_file():
                logger.error(f"Root metadata path is not a file: {root_path}")
                return False

            # Check file is readable
            if not root_path.stat().st_size > 0:
                logger.error(f"Root metadata file is empty: {root_path}")
                return False

            # Parse JSON
            try:
                with open(root_path, encoding="utf-8") as f:
                    root_data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Root metadata is not valid JSON: {e}")
                return False
            except UnicodeDecodeError as e:
                logger.error(f"Root metadata has encoding issues: {e}")
                return False

            # Validate required TUF root metadata structure
            required_fields = ["signed", "signatures"]
            for field in required_fields:
                if field not in root_data:
                    logger.error(f"Root metadata missing required field: {field}")
                    return False

            # Validate signed section
            signed = root_data["signed"]
            required_signed_fields = ["_type", "version", "expires", "keys", "roles"]
            for field in required_signed_fields:
                if field not in signed:
                    logger.error(f"Root metadata signed section missing required field: {field}")
                    return False

            # Validate metadata type
            if signed["_type"] != "root":
                logger.error(f"Root metadata has wrong type: {signed['_type']}")
                return False

            # Validate required roles
            required_roles = ["root", "targets", "snapshot", "timestamp"]
            roles = signed.get("roles", {})
            for role in required_roles:
                if role not in roles:
                    logger.error(f"Root metadata missing required role: {role}")
                    return False

            # Check expiration (with import here to avoid unused import)
            from datetime import datetime

            try:
                expires_str = signed["expires"]
                expires_date = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                if expires_date < datetime.now(expires_date.tzinfo):
                    logger.warning(f"Root metadata has expired: {expires_str}")
                    # Don't fail validation for expired metadata, just warn
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse expiration date: {e}")

            # Validate signatures exist
            signatures = root_data["signatures"]
            if not isinstance(signatures, list) or len(signatures) == 0:
                logger.error("Root metadata has no signatures")
                return False

            logger.debug(f"Root metadata validation successful: {root_path}")
            return True

        except Exception as e:
            logger.error(f"Root metadata validation failed: {e}")
            logger.debug("Root metadata validation error details:", exc_info=True)
            return False

    async def _validate_tuf_configuration(self) -> bool:
        """Validate TUF configuration before client initialization.

        Returns:
            bool: True if configuration is valid, False otherwise

        """
        try:
            logger.debug("Starting TUF configuration validation")

            # Validate repository URLs
            if not await self._validate_repository_urls():
                logger.error("Repository URL validation failed")
                return False

            # Validate TUF package version compatibility
            if not self._validate_tuf_package():
                logger.error("TUF package validation failed")
                return False

            # Validate configuration directory permissions
            if not self._validate_directory_permissions():
                logger.error("Directory permissions validation failed")
                return False

            logger.debug("TUF configuration validation completed successfully")
            return True

        except Exception as e:
            logger.error(f"TUF configuration validation failed: {e}")
            logger.debug("TUF configuration validation error details:", exc_info=True)
            return False

    def _validate_version_format(self, version: str) -> bool:
        """Validate version string format.

        Args:
            version: Version string to validate

        Returns:
            bool: True if valid, False otherwise

        """
        try:
            if not version or not isinstance(version, str):
                logger.error(f"Version is not a valid string: {version}")
                return False

            # Basic version format validation (semantic versioning)
            import re

            version_pattern = (
                r"^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9\-\.]+))?(?:\+([a-zA-Z0-9\-\.]+))?$"
            )
            if not re.match(version_pattern, version.strip()):
                logger.error(f"Version does not match semantic versioning format: {version}")
                return False

            logger.debug(f"Version format validation successful: {version}")
            return True

        except Exception as e:
            logger.error(f"Version format validation failed: {e}")
            return False

    def _validate_tuf_package(self) -> bool:
        """Validate TUF package installation and version.

        Returns:
            bool: True if valid, False otherwise

        """
        try:
            if not TUF_AVAILABLE:
                logger.error("TUF package is not available")
                return False

            import tufup

            version = getattr(tufup, "__version__", None)
            if not version:
                logger.warning("Could not determine tufup version")
                return True  # Don't fail if we can't get version

            logger.debug(f"TUF package validation successful: tufup {version}")
            return True

        except Exception as e:
            logger.error(f"TUF package validation failed: {e}")
            return False

    def _validate_directory_permissions(self) -> bool:
        """Validate directory permissions for TUF operations.

        Returns:
            bool: True if permissions are valid, False otherwise

        """
        try:
            # Test write permissions to config directory
            test_file = self.config_dir / ".tuf_permission_test"
            try:
                test_file.write_text("test", encoding="utf-8")
                test_file.unlink()
                logger.debug(f"Directory permissions validation successful: {self.config_dir}")
                return True
            except (PermissionError, OSError) as e:
                logger.error(f"No write permission to config directory {self.config_dir}: {e}")
                return False

        except Exception as e:
            logger.error(f"Directory permissions validation failed: {e}")
            return False

    async def _validate_repository_urls(self) -> bool:
        """Validate TUF repository URLs before using them.

        Returns:
            bool: True if URLs are valid, False otherwise

        """
        try:
            from urllib.parse import urlparse

            base_url = self.settings.tuf_repo_url
            if not base_url:
                logger.error("TUF repository URL is not configured")
                return False

            # Validate URL format
            parsed = urlparse(base_url)
            if not parsed.scheme or not parsed.netloc:
                logger.error(f"Invalid TUF repository URL format: {base_url}")
                return False

            if parsed.scheme not in ["http", "https"]:
                logger.error(f"TUF repository URL must use HTTP or HTTPS: {base_url}")
                return False

            logger.debug(f"URL format validation successful: {base_url}")

            # Test connectivity to metadata and targets endpoints
            metadata_url = f"{base_url.rstrip('/')}/metadata"
            targets_url = f"{base_url.rstrip('/')}/targets"

            # Test metadata URL
            try:
                logger.debug(f"Testing connectivity to metadata URL: {metadata_url}")
                response = await self._http_client.head(metadata_url, timeout=10.0)
                if response.status_code >= 500:
                    logger.warning(f"Metadata URL returned server error: {response.status_code}")
                    # Don't fail validation for server errors, just warn
                else:
                    logger.debug(
                        f"Metadata URL connectivity test successful: {response.status_code}"
                    )
            except Exception as e:
                logger.warning(f"Could not connect to metadata URL {metadata_url}: {e}")
                # Don't fail validation for connectivity issues, just warn

            # Test targets URL
            try:
                logger.debug(f"Testing connectivity to targets URL: {targets_url}")
                response = await self._http_client.head(targets_url, timeout=10.0)
                if response.status_code >= 500:
                    logger.warning(f"Targets URL returned server error: {response.status_code}")
                    # Don't fail validation for server errors, just warn
                else:
                    logger.debug(
                        f"Targets URL connectivity test successful: {response.status_code}"
                    )
            except Exception as e:
                logger.warning(f"Could not connect to targets URL {targets_url}: {e}")
                # Don't fail validation for connectivity issues, just warn

            # Validate SSL certificate for HTTPS URLs
            if parsed.scheme == "https":
                try:
                    import socket
                    import ssl

                    logger.debug(f"Validating SSL certificate for: {parsed.netloc}")
                    context = ssl.create_default_context()
                    with (
                        socket.create_connection(
                            (parsed.hostname, parsed.port or 443), timeout=10
                        ) as sock,
                        context.wrap_socket(sock, server_hostname=parsed.hostname) as ssock,
                    ):
                        cert = ssock.getpeercert()
                        if cert:
                            logger.debug("SSL certificate validation successful")
                        else:
                            logger.warning("Could not retrieve SSL certificate")
                except Exception as e:
                    logger.warning(f"SSL certificate validation failed: {e}")
                    # Don't fail validation for SSL issues, just warn

            logger.debug("Repository URL validation completed successfully")
            return True

        except Exception as e:
            logger.error(f"Repository URL validation failed: {e}")
            logger.debug("Repository URL validation error details:", exc_info=True)
            return False

    async def download_update(
        self, update_info: UpdateInfo, dest_dir: Path | None = None
    ) -> Path | None:
        """Download an update.

        Args:
            update_info: Information about the update to download
            dest_dir: Destination directory (uses temp dir if None)

        Returns:
            Path to downloaded file, or None if failed

        """
        try:
            if dest_dir is None:
                dest_dir = Path(tempfile.gettempdir()) / "accessiweather_updates"

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_file = dest_dir / update_info.artifact_name

            logger.info(f"Downloading update to {dest_file}")

            # The stream context manager is intentionally not awaited in tests using AsyncMock;
            # this code path is exercised in integration; tests use patching and may not await.
            async with self._http_client.stream("GET", update_info.download_url) as response:
                response.raise_for_status()

                with open(dest_file, "wb") as f:
                    async for chunk in response.aiter_bytes():
                        f.write(chunk)

            logger.info(f"Update downloaded successfully: {dest_file}")
            return dest_file

        except Exception as e:
            logger.error(f"Failed to download update: {e}")
            return None

    def get_tuf_diagnostics(self) -> dict:
        """Get detailed TUF diagnostics for troubleshooting.

        Returns:
            dict: Diagnostic information about TUF availability and status

        """
        diagnostics = {
            "tuf_available": TUF_AVAILABLE,
            "tufup_installed": False,
            "tufup_version": None,
            "import_error": None,
            "installation_command": "pip install tufup",
            "client_initialized": self._tuf_initialized,
            "configuration_valid": False,
            "root_metadata_valid": False,
            "repository_urls_valid": False,
            "directory_permissions_valid": False,
            "version_format_valid": False,
        }

        try:
            import tufup

            diagnostics["tufup_installed"] = True
            diagnostics["tufup_version"] = getattr(tufup, "__version__", "unknown")

            # Test basic TUF client importability without binding the symbol
            import importlib.util

            diagnostics["client_import_success"] = (
                importlib.util.find_spec("tufup.client") is not None
            )

            # Test configuration validation components
            try:
                # Test TUF package validation
                diagnostics["tuf_package_valid"] = self._validate_tuf_package()

                # Test directory permissions
                diagnostics["directory_permissions_valid"] = self._validate_directory_permissions()

                # Test version format
                diagnostics["version_format_valid"] = self._validate_version_format(__version__)

                # Test root metadata if it exists
                tuf_dir = self.config_dir / "tuf" / "metadata"
                root_path = tuf_dir / "root.json"
                if root_path.exists():
                    diagnostics["root_metadata_valid"] = self._validate_root_json(root_path)
                    diagnostics["root_metadata_path"] = str(root_path)
                else:
                    diagnostics["root_metadata_path"] = "Not found"

                # Add repository URL information
                diagnostics["repository_url"] = self.settings.tuf_repo_url
                diagnostics["metadata_url"] = f"{self.settings.tuf_repo_url.rstrip('/')}/metadata"
                diagnostics["targets_url"] = f"{self.settings.tuf_repo_url.rstrip('/')}/targets"

                # Add configuration directory information
                diagnostics["config_directory"] = str(self.config_dir)
                diagnostics["tuf_directory"] = str(self.config_dir / "tuf")

                # Add current version information
                diagnostics["current_version"] = __version__

            except Exception as e:
                diagnostics["validation_error"] = str(e)

        except ImportError as e:
            diagnostics["import_error"] = str(e)
            diagnostics["client_import_success"] = False

        return diagnostics

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await self._http_client.aclose()
            logger.info("Update service cleaned up")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    def __del__(self):
        """Destructor to ensure cleanup without emitting warnings.

        We only schedule aclose() if an event loop is running; otherwise, we
        avoid constructing the coroutine to prevent 'never awaited' warnings.
        """
        try:
            if hasattr(self, "_http_client") and self._http_client:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    loop.create_task(self._http_client.aclose())
        except Exception:
            # Best-effort cleanup; ignore errors at interpreter shutdown
            pass
