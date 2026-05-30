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
# Paths that ship inside the build surface but never warrant a release note.
# Checked before USER_FACING_PATH_PREFIXES, so these win even though they live
# under src/. Extend this as recurring false positives show up.
EXCLUDED_PATH_PREFIXES = (
    "src/accessiweather/weather_gov_api_client/",  # generated NWS API client
)
USER_FACING_PATHS = {
    "accessiweather.spec",
    "pyproject.toml",
    "scripts/generate_build_meta.py",
}
USER_FACING_SUFFIXES = (".spec",)
# Markers a commit message can carry to opt its change set out of the gate.
# Used for direct pushes, where there is no PR label to apply.
SKIP_CHANGELOG_MARKERS = ("changelog: none", "[skip changelog]")
NIGHTLY_BUILD_MARKERS = ("nightly: build", "[nightly build]")
SECTION_ORDER = ("Added", "Changed", "Fixed", "Improved", "Removed", "Deprecated", "Security")
PYPROJECT_METADATA_FIELDS_WITHOUT_CHANGELOG = {"version", "description"}
PYPROJECT_TOOLING_REQUIREMENTS_WITHOUT_CHANGELOG = {"pyright", "ruff"}


@dataclass(frozen=True)
class ChangelogSection:
    title: str
    entries: tuple[str, ...]


def run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8").strip()


def output_lines(output: str) -> list[str]:
    return [line for line in output.splitlines() if line]


def dedupe_preserving_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def is_user_facing_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith(EXCLUDED_PATH_PREFIXES):
        return False
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


def changed_lines_from_diff(diff: str) -> list[str]:
    changed_lines: list[str] = []
    for line in diff.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith(("+", "-")):
            changed_lines.append(line[1:].strip())
    return changed_lines


def pyproject_change_requires_changelog(
    base: str,
    head: str,
    include_worktree: bool = False,
) -> bool:
    diffs = [run_git(["diff", "--unified=0", f"{base}..{head}", "--", "pyproject.toml"])]
    if include_worktree:
        diffs.append(run_git(["diff", "--unified=0", "HEAD", "--", "pyproject.toml"]))
    changed_lines = [line for diff in diffs for line in changed_lines_from_diff(diff)]
    return pyproject_changed_lines_require_changelog(changed_lines)


def requires_changelog_entry(
    path: str,
    base: str,
    head: str,
    include_worktree: bool = False,
) -> bool:
    normalized = path.replace("\\", "/")
    if normalized == "pyproject.toml":
        return pyproject_change_requires_changelog(base, head, include_worktree)
    return is_user_facing_path(normalized)


def worktree_changed_files() -> list[str]:
    tracked = output_lines(run_git(["diff", "--name-only", "HEAD"]))
    untracked = output_lines(run_git(["ls-files", "--others", "--exclude-standard"]))
    return dedupe_preserving_order([*tracked, *untracked])


def changed_files(
    base: str,
    head: str,
    worktree_files: list[str] | None = None,
) -> list[str]:
    committed = output_lines(run_git(["diff", "--name-only", f"{base}..{head}"]))
    if worktree_files is None:
        return committed
    return dedupe_preserving_order([*committed, *worktree_files])


def current_branch() -> str:
    return run_git(["branch", "--show-current"])


def resolve_base(base: str) -> str:
    if base != "auto":
        return base
    if current_branch() == "main":
        return "origin/main"
    return "origin/dev"


def messages_opt_out_of_changelog(messages: list[str]) -> bool:
    """
    Return True only when every commit message opts out of the gate.

    Requiring all commits (rather than any) prevents a single skip marker from
    silently exempting a change set that also contains user-facing work.
    """
    if not messages:
        return False
    return all(
        any(marker in message.casefold() for marker in SKIP_CHANGELOG_MARKERS)
        for message in messages
    )


def commit_messages(base: str, head: str) -> list[str]:
    log = run_git(["log", "--no-merges", "--format=%H", f"{base}..{head}"])
    hashes = [line for line in log.splitlines() if line]
    return [run_git(["show", "-s", "--format=%B", commit]) for commit in hashes]


def commits_opt_out_of_changelog(base: str, head: str) -> bool:
    return messages_opt_out_of_changelog(commit_messages(base, head))


def messages_request_nightly_build(messages: list[str]) -> bool:
    return any(
        any(marker in message.casefold() for marker in NIGHTLY_BUILD_MARKERS)
        for message in messages
    )


def commits_request_nightly_build(base: str, head: str) -> bool:
    return messages_request_nightly_build(commit_messages(base, head))


def unreleased_added_entries(base: str, head: str, include_worktree: bool = False) -> list[str]:
    base_entries = {
        normalize_entry(entry)
        for section in parse_sections(
            extract_release_block(changelog_at(base), r"^## \[?Unreleased\]?.*$")
        )
        for entry in section.entries
    }
    if include_worktree:
        head_text = CHANGELOG_PATH.read_text(encoding="utf-8")
    else:
        head_text = run_git(["show", f"{head}:{CHANGELOG_PATH.as_posix()}"])
    return [
        entry
        for section in parse_sections(extract_release_block(head_text, r"^## \[?Unreleased\]?.*$"))
        for entry in section.entries
        if normalize_entry(entry) not in base_entries
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


def excluded_entries_from_notes(path: str) -> set[str]:
    if not path:
        return set()
    return {
        normalize_entry(entry)
        for section in parse_sections(Path(path).read_text(encoding="utf-8"))
        for entry in section.entries
    }


def check_command(args: argparse.Namespace) -> int:
    base = resolve_base(args.base)
    should_check_worktree = args.head == "HEAD" and not getattr(args, "committed_only", False)
    worktree_files = worktree_changed_files() if should_check_worktree else []
    include_worktree = bool(worktree_files)
    files = changed_files(base, args.head, worktree_files if include_worktree else None)
    user_facing = [
        path for path in files if requires_changelog_entry(path, base, args.head, include_worktree)
    ]
    if not user_facing:
        print("No user-facing paths changed.")
        return 0

    worktree_user_facing = [
        path
        for path in worktree_files
        if requires_changelog_entry(path, "HEAD", "HEAD", include_worktree)
    ]
    if not worktree_user_facing and commits_opt_out_of_changelog(base, args.head):
        print("All commits opt out of the changelog gate via a skip marker.")
        return 0

    if CHANGELOG_PATH.as_posix() not in files:
        print("User-facing paths changed without updating CHANGELOG.md:", file=sys.stderr)
        for path in user_facing:
            print(f"- {path}", file=sys.stderr)
        return 1

    entries = unreleased_added_entries(base, args.head, include_worktree)
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
        excluded_entries = excluded_entries_from_notes(args.exclude_notes)
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


def should_build_nightly_command(args: argparse.Namespace) -> int:
    if not args.previous_tag:
        print("should_build=true")
        print("No previous nightly tag found; building once.", file=sys.stderr)
        return 0

    if commits_request_nightly_build(args.previous_tag, args.head):
        print("should_build=true")
        print("Nightly build requested by commit marker.", file=sys.stderr)
        return 0

    changelog_text = CHANGELOG_PATH.read_text(encoding="utf-8")
    sections = sections_added_since(
        args.previous_tag,
        changelog_text,
        excluded_entries_from_notes(args.exclude_notes),
    )
    if sections:
        print("should_build=true")
        print("New curated changelog entries found for nightly build.", file=sys.stderr)
    else:
        print("should_build=false")
        print("No new curated changelog entries or nightly build marker found.", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and extract curated changelog entries.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Require Unreleased changelog entries.")
    check.add_argument(
        "--base",
        required=True,
        help="Base ref to compare against, or 'auto' for origin/main on main and origin/dev otherwise.",
    )
    check.add_argument("--head", default="HEAD")
    check.add_argument(
        "--committed-only",
        action="store_true",
        help="Ignore uncommitted working-tree changes during local checks.",
    )
    check.set_defaults(func=check_command)

    notes = subparsers.add_parser("notes", help="Generate release notes from CHANGELOG.md.")
    notes.add_argument("--kind", choices=("nightly", "stable"), required=True)
    notes.add_argument("--version", default="")
    notes.add_argument("--previous-tag", default="")
    notes.add_argument("--exclude-notes", default="")
    notes.add_argument("--output", default="notes.md")
    notes.set_defaults(func=notes_command)

    should_build = subparsers.add_parser(
        "should-build-nightly",
        help="Decide whether a scheduled nightly should build artifacts.",
    )
    should_build.add_argument("--previous-tag", default="")
    should_build.add_argument("--exclude-notes", default="")
    should_build.add_argument("--head", default="HEAD")
    should_build.set_defaults(func=should_build_nightly_command)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
