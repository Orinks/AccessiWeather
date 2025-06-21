"""Update information data structure for AccessiWeather.

This module contains the UpdateInfo class that holds information about
available updates.
"""


class UpdateInfo:
    """Information about an available update."""

    def __init__(
        self,
        version: str,
        release_url: str,
        release_notes: str,
        assets: list[dict],
        published_date: str,
        is_prerelease: bool = False,
    ):
        self.version = version
        self.release_url = release_url
        self.release_notes = release_notes
        self.assets = assets
        self.published_date = published_date
        self.is_prerelease = is_prerelease

        # Parse assets for installer and portable versions
        self.installer_asset = None
        self.portable_asset = None

        for asset in assets:
            name = asset.get("name", "").lower()
            if "setup" in name and name.endswith(".exe"):
                self.installer_asset = asset
            elif "portable" in name and name.endswith(".zip"):
                self.portable_asset = asset
