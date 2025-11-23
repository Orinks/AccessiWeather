from accessiweather.services.update_service.releases import ReleaseManager

# Sample release data
STABLE_RELEASE = {"tag_name": "v1.0.0", "prerelease": False}
BETA_RELEASE = {"tag_name": "v1.1.0-beta.1", "prerelease": True}
RC_RELEASE = {"tag_name": "v1.1.0-rc.1", "prerelease": True}
NIGHTLY_RELEASE = {"tag_name": "nightly-20231025", "prerelease": True}
# A prerelease that is neither beta nor rc nor nightly
RANDOM_PRERELEASE = {"tag_name": "v1.2.0-alpha.1", "prerelease": True}

ALL_RELEASES = [
    STABLE_RELEASE,
    BETA_RELEASE,
    RC_RELEASE,
    NIGHTLY_RELEASE,
    RANDOM_PRERELEASE,
]


class TestReleaseManagerNightly:
    # Tests for filter_releases_by_channel

    def test_filter_releases_stable(self):
        """Verify stable channel filters out beta, rc, and nightly releases."""
        filtered = ReleaseManager.filter_releases_by_channel(ALL_RELEASES, "stable")
        assert STABLE_RELEASE in filtered
        assert len(filtered) == 1
        assert BETA_RELEASE not in filtered
        assert NIGHTLY_RELEASE not in filtered
        assert RC_RELEASE not in filtered
        assert RANDOM_PRERELEASE not in filtered

    def test_filter_releases_dev(self):
        """Verify dev channel includes all releases (stable, beta, rc, nightly)."""
        filtered = ReleaseManager.filter_releases_by_channel(ALL_RELEASES, "dev")
        assert len(filtered) == len(ALL_RELEASES)
        for release in ALL_RELEASES:
            assert release in filtered

    def test_filter_releases_invalid_channel(self):
        """Verify invalid channel falls back to "stable"."""
        filtered = ReleaseManager.filter_releases_by_channel(ALL_RELEASES, "super_unstable")
        # Should behave like stable
        assert STABLE_RELEASE in filtered
        assert len(filtered) == 1
        assert NIGHTLY_RELEASE not in filtered

    # Tests for _is_newer_version

    def test_is_newer_nightly_vs_nightly(self):
        """Nightly vs Nightly (newer date > older date)."""
        # newer > older -> True
        assert ReleaseManager._is_newer_version("nightly-20240102", "nightly-20240101") is True
        # older > newer -> False
        assert ReleaseManager._is_newer_version("nightly-20240101", "nightly-20240102") is False
        # same -> False
        assert ReleaseManager._is_newer_version("nightly-20240101", "nightly-20240101") is False

    def test_is_newer_nightly_vs_stable(self):
        """Nightly vs Stable (nightly candidate > stable current)."""
        # If candidate is nightly and current is not, return True
        assert ReleaseManager._is_newer_version("nightly-20240101", "v1.0.0") is True
        # Even if stable version seems "higher" in semver, nightly takes precedence in this logic
        assert ReleaseManager._is_newer_version("nightly-20240101", "v99.0.0") is True

    def test_is_newer_stable_vs_nightly(self):
        """Stable vs Nightly (stable candidate < nightly current - i.e., don't auto-downgrade)."""
        # If candidate is not nightly and current is, return False
        assert ReleaseManager._is_newer_version("v2.0.0", "nightly-20240101") is False
        assert ReleaseManager._is_newer_version("v1.0.0", "nightly-20240101") is False

    def test_is_newer_stable_vs_stable(self):
        """Stable vs Stable (standard semver)."""
        assert ReleaseManager._is_newer_version("v1.1.0", "v1.0.0") is True
        assert ReleaseManager._is_newer_version("1.1.0", "1.0.0") is True
        assert ReleaseManager._is_newer_version("v1.0.0", "v1.1.0") is False
        assert ReleaseManager._is_newer_version("v1.0.0", "v1.0.0") is False

        # Prerelease comparison
        assert ReleaseManager._is_newer_version("v1.1.0", "v1.1.0-beta.1") is True
        assert ReleaseManager._is_newer_version("v1.1.0-beta.2", "v1.1.0-beta.1") is True

    def test_is_newer_invalid(self):
        """Invalid versions handled gracefully."""
        # Should return False if parsing fails
        assert ReleaseManager._is_newer_version("invalid_ver", "v1.0.0") is False
        assert ReleaseManager._is_newer_version("v1.0.0", "invalid_ver") is False
        assert ReleaseManager._is_newer_version("foo", "bar") is False

    def test_is_newer_invalid_tags_soft_fail(self):
        """Test that invalid tags or parsing failures result in False (soft fail)."""
        # 1. Invalid tag vs valid version
        assert ReleaseManager._is_newer_version("invalid-tag", "1.0.0") is False

        # 2. Valid version vs invalid tag
        assert ReleaseManager._is_newer_version("1.0.0", "invalid-tag") is False

        # 3. Broken nightly tag (suffix parsing fails)
        # This relies on _parse_nightly_suffix returning None for "nightly-broken"
        # and _is_newer_version handling that gracefully.
        assert ReleaseManager._is_newer_version("nightly-broken", "1.0.0") is False
