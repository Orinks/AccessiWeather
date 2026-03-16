"""Extract curated public release notes from CHANGELOG.md."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INTERNAL_BULLET_PATTERN = re.compile(
    r"(?i)\b("
    r"ci|coverage|test(?:s|ing)?|workflow|cron|refactor|internal|developer-facing|"
    r"docs?|documentation|antfarm|release note|changelog"
    r")\b"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract a user-facing release note section from CHANGELOG.md."
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=Path("CHANGELOG.md"),
        help="Path to the changelog file.",
    )
    parser.add_argument(
        "--mode",
        choices=("nightly", "stable"),
        required=True,
        help="Section to extract: nightly uses 'Unreleased', stable uses a version heading.",
    )
    parser.add_argument(
        "--version",
        help="Stable version to extract (required when --mode=stable).",
    )
    parser.add_argument(
        "--default-message",
        required=True,
        help="Fallback text when the requested section is missing or empty.",
    )
    return parser.parse_args()


def _extract_section(lines: list[str], heading_pattern: re.Pattern[str]) -> str | None:
    start_index: int | None = None
    for index, line in enumerate(lines):
        if heading_pattern.match(line):
            start_index = index + 1
            break

    if start_index is None:
        return None

    section_lines: list[str] = []
    for line in lines[start_index:]:
        if line.startswith("## "):
            break
        section_lines.append(line)

    return "\n".join(section_lines).strip()


def _is_internal_bullet(line: str) -> bool:
    stripped = line.lstrip()
    if not stripped.startswith("- "):
        return False
    return bool(INTERNAL_BULLET_PATTERN.search(stripped[2:]))


def sanitize_release_notes(section: str) -> str:
    if not section.strip():
        return ""

    output_lines: list[str] = []
    pending_heading: str | None = None
    pending_block: list[str] = []
    skip_nested_bullets = False

    def flush_heading() -> None:
        nonlocal pending_heading, pending_block
        if pending_heading and pending_block:
            if output_lines and output_lines[-1] != "":
                output_lines.append("")
            output_lines.append(pending_heading)
            output_lines.extend(pending_block)
        pending_heading = None
        pending_block = []

    for line in section.splitlines():
        stripped = line.strip()

        if line.startswith("### "):
            flush_heading()
            pending_heading = line
            skip_nested_bullets = False
            continue

        if not stripped:
            if pending_heading:
                if pending_block and pending_block[-1] != "":
                    pending_block.append("")
            elif output_lines and output_lines[-1] != "":
                output_lines.append("")
            skip_nested_bullets = False
            continue

        if stripped == "---":
            skip_nested_bullets = False
            continue

        if _is_internal_bullet(line):
            skip_nested_bullets = True
            continue

        if skip_nested_bullets and line.startswith(("  - ", "    - ", "\t- ")):
            continue

        skip_nested_bullets = False
        if pending_heading:
            pending_block.append(line)
        else:
            output_lines.append(line)

    flush_heading()
    return "\n".join(output_lines).strip()


def extract_release_notes(
    changelog_text: str,
    *,
    mode: str,
    version: str | None = None,
) -> str | None:
    lines = changelog_text.splitlines()

    if mode == "nightly":
        pattern = re.compile(r"^##\s+Unreleased\s*$")
        section = _extract_section(lines, pattern)
        return sanitize_release_notes(section or "")

    if not version:
        raise ValueError("Stable mode requires a version.")

    normalized_version = version.removeprefix("v")
    pattern = re.compile(
        rf"^##\s+\[{re.escape(normalized_version)}\](?:\s+-\s+.+)?\s*$"
    )
    section = _extract_section(lines, pattern)
    return sanitize_release_notes(section or "")


def main() -> int:
    args = parse_args()

    try:
        changelog_text = args.changelog.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Failed to read changelog: {exc}", file=sys.stderr)
        return 1

    try:
        notes = extract_release_notes(
            changelog_text,
            mode=args.mode,
            version=args.version,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    output = notes.strip() if notes else args.default_message.strip()
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
