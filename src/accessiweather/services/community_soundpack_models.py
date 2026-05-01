"""Models for community sound pack discovery."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(order=True)
class CommunityPack:
    """Metadata describing a community sound pack."""

    name: str
    author: str
    description: str
    version: str
    download_url: str
    file_size: int | None
    repository_url: str
    release_tag: str
    download_count: int | None = None
    created_date: str | None = None
    preview_image_url: str | None = None
    repo_path: str | None = None
    tree_sha: str | None = None
    ref: str | None = "main"

    def __str__(self) -> str:
        return f"{self.name} {self.version} by {self.author}"
