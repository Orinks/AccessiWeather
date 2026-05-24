from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

CHANGELOG_PATH = Path("CHANGELOG.md")
USER_FACING_PATH_PREFIXES = (
    "src/",
    "installer/",
    "soundpacks/",
)
USER_FACING_PATHS = {
    "accessiweather.spec",
    "pyproject.toml",
    "scripts/generate_build_meta.py",
}
USER_FACING_SUFFIXES = (".spec",)
SECTION_ORDER = ("Added", "Changed", "Fixed", "Improved", "Removed", "Deprecated", "Security")
PYPROJECT_METADATA_FIELDS_WITHOUT_CHANGELOG = {"version", "description"}
PYPROJECT_TOOLING_REQUIREMENTS_WITHOUT_CHANGELOG = {"pyright", "ruff"}


@dataclass(frozen=True)
class ChangelogSection:
    title: str
    entries: tuple[str, ...]


def run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8").strip()


def is_user_facing_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return (
        normalized in USER_FACING_PATHS
        or normalized.endswith(USER_FACING_SUFFIXES)
        or normalized.startswith(USER_FACING_PATH_PREFIXES)
    )


def pyproject_changed_lines_require_changelog(changed_lines: list[str]) -> bool:
    for line in changed_lines:
        requirement_match = re.match(r'"([A-Za-z0-9_.-]+)', line)
        if (
            requirement_match
            and requirement_match.group(1).casefold()
            in PYPROJECT_TOOLING_REQUIREMENTS_WITHOUT_CHANGELOG
        ):
            continue
        field = line.split("=", 1)[0].strip()
        if field not in PYPROJECT_METADATA_FIELDS_WITHOUT_CHANGELOG:
            return True
    return False


def pyproject_change_requires_changelog(base: str, head: str) -> bool:
    diff = run_git(["diff", "--unified=0", f"{base}..{head}", "--", "pyproject.toml"])
    changed_lines: list[str] = []
    for line in diff.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith(("+", "-")):
            changed_lines.append(line[1:].strip())
    return pyproject_changed_lines_require_changelog(changed_lines)


def requires_changelog_entry(path: str, base: str, head: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized == "pyproject.toml":
        return pyproject_change_requires_changelog(base, head)
    return is_user_facing_path(normalized)


def changed_files(base: str, head: str) -> list[str]:
    output = run_git(["diff", "--name-only", f"{base}..{head}"])
    return [line for line in output.splitlines() if line]


def unreleased_added_entries(base: str, head: str) -> list[str]:
    base_entries = {
        entry
        for section in parse_sections(
            extract_release_block(changelog_at(base), r"^## \[?Unreleased\]?.*$")
        )
        for entry in section.entries
    }
    head_text = run_git(["show", f"{head}:{CHANGELOG_PATH.as_posix()}"])
    return [
        entry
        for section in parse_sections(extract_release_block(head_text, r"^## \[?Unreleased\]?.*$"))
        for entry in section.entries
        if entry not in base_entries
    ]


def extract_release_block(text: str, heading_pattern: str) -> str:
    match = re.search(heading_pattern, text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^## ", text[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def parse_sections(markdown: str) -> list[ChangelogSection]:
    sections: list[ChangelogSection] = []
    current_title = ""
    current_entries: list[str] = []
    current_entry: list[str] = []

    def flush_entry() -> None:
        nonlocal current_entry
        if current_entry:
            current_entries.append("\n".join(current_entry).rstrip())
            current_entry = []

    def flush_section() -> None:
        nonlocal current_entries
        flush_entry()
        if current_title and current_entries:
            sections.append(ChangelogSection(current_title, tuple(current_entries)))
        current_entries = []

    for line in markdown.splitlines():
        heading = re.match(r"^#{2,3}\s+(.+?)\s*$", line)
        if heading:
            flush_section()
            current_title = heading.group(1)
            continue

        if re.match(r"^-\s+", line):
            flush_entry()
            current_entry.append(line)
            continue

        if current_entry and (line.startswith("  ") or not line.strip()):
            current_entry.append(line)

    flush_section()
    return sections


def format_sections(sections: list[ChangelogSection]) -> str:
    if not sections:
        return "- No user-facing changes"

    by_title = {section.title: section.entries for section in sections}
    ordered_titles = [title for title in SECTION_ORDER if title in by_title]
    ordered_titles.extend(
        section.title for section in sections if section.title not in ordered_titles
    )

    chunks: list[str] = []
    for title in ordered_titles:
        entries = by_title[title]
        chunks.append(f"## {title}\n" + "\n".join(dict.fromkeys(entries)))
    return "\n\n".join(chunks).strip()


def normalize_entry(entry: str) -> str:
    entry = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", entry)
    entry = re.sub(r"`([^`]+)`", r"\1", entry)
    entry = re.sub(r"\*\*([^*]+)\*\*", r"\1", entry)
    entry = re.sub(r"__([^_]+)__", r"\1", entry)
    entry = re.sub(r"\*([^*]+)\*", r"\1", entry)
    entry = re.sub(r"_([^_]+)_", r"\1", entry)
    entry = re.sub(r"^[-*+]\s+", "", entry.strip())
    entry = re.sub(r"\s+[-\u2013\u2014]\s+", " - ", entry)
    entry = re.sub(r"\s+", " ", entry)
    return entry.casefold().strip()


def changelog_at(ref: str) -> str:
    try:
        return run_git(["show", f"{ref}:{CHANGELOG_PATH.as_posix()}"])
    except subprocess.CalledProcessError:
        return ""


def sections_added_since(
    base_ref: str,
    head_text: str,
    extra_excluded_entries: set[str] | None = None,
) -> list[ChangelogSection]:
    base_entries = {
        normalize_entry(entry)
        for section in parse_sections(
            extract_release_block(changelog_at(base_ref), r"^## \[?Unreleased\]?.*$")
        )
        for entry in section.entries
    }
    if extra_excluded_entries:
        base_entries.update(extra_excluded_entries)

    added_sections: list[ChangelogSection] = []

    for section in parse_sections(extract_release_block(head_text, r"^## \[?Unreleased\]?.*$")):
        entries = tuple(
            entry for entry in section.entries if normalize_entry(entry) not in base_entries
        )
        if entries:
            added_sections.append(ChangelogSection(section.title, entries))

    return added_sections


def check_command(args: argparse.Namespace) -> int:
    files = changed_files(args.base, args.head)
    user_facing = [path for path in files if requires_changelog_entry(path, args.base, args.head)]
    if not user_facing:
        print("No user-facing paths changed.")
        return 0

    if CHANGELOG_PATH.as_posix() not in files:
        print("User-facing paths changed without updating CHANGELOG.md:", file=sys.stderr)
        for path in user_facing:
            print(f"- {path}", file=sys.stderr)
        return 1

    entries = unreleased_added_entries(args.base, args.head)
    if not entries:
        print(
            "CHANGELOG.md changed, but no new bullet was added under ## [Unreleased].",
            file=sys.stderr,
        )
        return 1

    print("Found CHANGELOG.md Unreleased entries for user-facing changes.")
    return 0


def notes_command(args: argparse.Namespace) -> int:
    changelog_text = CHANGELOG_PATH.read_text(encoding="utf-8")
    if args.kind == "nightly":
        excluded_entries: set[str] = set()
        if args.exclude_notes:
            excluded_entries = {
                normalize_entry(entry)
                for section in parse_sections(Path(args.exclude_notes).read_text(encoding="utf-8"))
                for entry in section.entries
            }
        if not args.previous_tag:
            notes = format_sections(
                parse_sections(extract_release_block(changelog_text, r"^## \[?Unreleased\]?.*$"))
            )
        else:
            notes = format_sections(
                sections_added_since(args.previous_tag, changelog_text, excluded_entries)
            )
    else:
        version = args.version.removeprefix("v")
        block = extract_release_block(
            changelog_text,
            rf"^## \[{re.escape(version)}\](?:\s+-\s+\d{{4}}-\d{{2}}-\d{{2}})?\s*$",
        )
        if not block:
            block = extract_release_block(changelog_text, r"^## \[?Unreleased\]?.*$")
        notes = format_sections(parse_sections(block))

    Path(args.output).write_text(notes + "\n", encoding="utf-8")
    print(f"Wrote release notes to {args.output}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and extract curated changelog entries.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Require Unreleased changelog entries.")
    check.add_argument("--base", required=True)
    check.add_argument("--head", default="HEAD")
    check.set_defaults(func=check_command)

    notes = subparsers.add_parser("notes", help="Generate release notes from CHANGELOG.md.")
    notes.add_argument("--kind", choices=("nightly", "stable"), required=True)
    notes.add_argument("--version", default="")
    notes.add_argument("--previous-tag", default="")
    notes.add_argument("--exclude-notes", default="")
    notes.add_argument("--output", default="notes.md")
    notes.set_defaults(func=notes_command)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
