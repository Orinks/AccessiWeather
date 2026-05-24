"""Quality checks for recorded integration-test cassettes."""

from __future__ import annotations

import textwrap

import pytest

from tests.integration.conftest import find_unexpected_cassette_api_errors


@pytest.mark.integration
def test_recorded_cassettes_do_not_contain_unexpected_api_errors(vcr_cassette_dir):
    """Guard replay tests against silently accepting provider-side error recordings."""
    failures = find_unexpected_cassette_api_errors(vcr_cassette_dir)

    assert failures == []


@pytest.mark.integration
def test_cassette_audit_flags_unexpected_http_errors(tmp_path):
    """A success cassette with an HTTP error response must be reported."""
    cassette = tmp_path / "provider" / "unexpected_500.yaml"
    cassette.parent.mkdir()
    cassette.write_text(
        textwrap.dedent(
            """
            interactions:
            - request:
                method: GET
                uri: https://api.example.test/weather
              response:
                body:
                  string: '{"detail":"upstream failed"}'
                headers:
                  Content-Type:
                  - application/json
                status:
                  code: 500
                  message: Internal Server Error
            version: 1
            """
        ).strip(),
        encoding="utf-8",
    )

    failures = find_unexpected_cassette_api_errors(tmp_path)

    assert len(failures) == 1
    assert failures[0].relative_path == "provider/unexpected_500.yaml"
    assert failures[0].status_code == 500
