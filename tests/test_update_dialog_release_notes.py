from __future__ import annotations

from accessiweather.ui.dialogs.update_dialog import format_release_notes_for_dialog


def test_format_release_notes_for_dialog_removes_markdown_noise() -> None:
    raw_notes = """## Added
- **National Products** now use `IEM AFOS` text.
- See [CHANGELOG.md](https://example.com/changelog) for details.

## Fixed
- Pirate Weather handles _freezing rain_ correctly.
"""

    assert format_release_notes_for_dialog(raw_notes) == (
        "Added\n"
        "- National Products now use IEM AFOS text.\n"
        "- See CHANGELOG.md for details.\n"
        "\n"
        "Fixed\n"
        "- Pirate Weather handles freezing rain correctly."
    )


def test_format_release_notes_for_dialog_handles_empty_notes() -> None:
    assert format_release_notes_for_dialog("") == "No release notes available."


def test_format_release_notes_for_dialog_keeps_plain_bullets() -> None:
    raw_notes = """### Changed
1. First numbered item.
* Second starred item.
"""

    assert format_release_notes_for_dialog(raw_notes) == (
        "Changed\n- First numbered item.\n- Second starred item."
    )
