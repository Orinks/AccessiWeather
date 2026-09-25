//! `scripts/changelog_tools.py`: the CHANGELOG gate for pull requests,
//! release notes from curated `CHANGELOG.md` entries, and the nightly
//! should-build decision.
//!
//! The Rust edition's shipped trees (`rust/crates/`, `rust/packaging/`) count
//! as user-facing too; everything else matches the Python tool.

use std::collections::HashSet;
use std::io::Write;
use std::path::Path;
use std::process::{Command as Process, Stdio};
use std::sync::LazyLock;

use clap::{Subcommand, ValueEnum};
use regex::Regex;

use crate::Result;

const CHANGELOG_PATH: &str = "CHANGELOG.md";
const USER_FACING_PATH_PREFIXES: [&str; 5] = [
    "src/",
    "installer/",
    "soundpacks/",
    "rust/crates/",
    "rust/packaging/",
];
/// Paths that ship inside the build surface but never warrant a release note.
const EXCLUDED_PATH_PREFIXES: [&str; 1] = ["src/accessiweather/weather_gov_api_client/"];
const USER_FACING_PATHS: [&str; 3] = [
    "accessiweather.spec",
    "pyproject.toml",
    "scripts/generate_build_meta.py",
];
const USER_FACING_SUFFIXES: [&str; 1] = [".spec"];
const SKIP_CHANGELOG_MARKERS: [&str; 2] = ["changelog: none", "[skip changelog]"];
const NIGHTLY_BUILD_MARKERS: [&str; 2] = ["nightly: build", "[nightly build]"];
const SECTION_ORDER: [&str; 7] = [
    "Added",
    "Changed",
    "Fixed",
    "Improved",
    "Removed",
    "Deprecated",
    "Security",
];
const PYPROJECT_METADATA_FIELDS_WITHOUT_CHANGELOG: [&str; 2] = ["version", "description"];
const PYPROJECT_TOOLING_REQUIREMENTS_WITHOUT_CHANGELOG: [&str; 2] = ["pyright", "ruff"];
const UNRELEASED: &str = r"^## \[?Unreleased\]?.*$";
const STAGED_HINT: &str = "Add a bullet under ## [Unreleased] in CHANGELOG.md, or put `Changelog: none` in the commit message if nothing user-facing changed.";

#[derive(Subcommand)]
pub enum Command {
    /// Require Unreleased changelog entries.
    Check {
        /// Base ref to compare against, or 'auto' for origin/main on main and origin/dev otherwise.
        #[arg(long)]
        base: String,
        #[arg(long, default_value = "HEAD")]
        head: String,
        /// Ignore uncommitted working-tree changes during local checks.
        #[arg(long)]
        committed_only: bool,
        /// Check the commit being made (the `commit-msg` hook): HEAD plus the
        /// index, with the new commit's message read from MESSAGE_FILE.
        #[arg(long, value_name = "MESSAGE_FILE")]
        staged: Option<String>,
    },
    /// Generate release notes from CHANGELOG.md.
    Notes {
        #[arg(long, value_enum)]
        kind: Kind,
        #[arg(long, default_value = "")]
        version: String,
        #[arg(long, default_value = "")]
        previous_tag: String,
        #[arg(long, default_value = "")]
        exclude_notes: String,
        #[arg(long, default_value = "notes.md")]
        output: String,
    },
    /// Decide whether a scheduled nightly should build artifacts.
    ShouldBuildNightly {
        #[arg(long, default_value = "")]
        previous_tag: String,
        #[arg(long, default_value = "")]
        exclude_notes: String,
        #[arg(long, default_value = "")]
        latest_stable_tag: String,
        #[arg(long, default_value = "")]
        exclude_stable_notes: String,
        #[arg(long, default_value = "HEAD")]
        head: String,
    },
}

#[derive(Clone, Copy, PartialEq, Eq, ValueEnum)]
pub enum Kind {
    Nightly,
    Stable,
}

/// Run a changelog command against the repository at `root`; the result is
/// the process exit code.
pub fn run(root: &Path, cmd: Command, out: &mut dyn Write, err: &mut dyn Write) -> Result<u8> {
    let git = Git(root);
    match cmd {
        Command::Check {
            base,
            head,
            committed_only,
            staged,
        } => {
            let code = check(
                &git,
                &base,
                &head,
                committed_only,
                staged.as_deref(),
                out,
                err,
            )?;
            if code != 0 && staged.is_some() {
                writeln!(err, "{STAGED_HINT}")?;
            }
            Ok(code)
        }
        Command::Notes {
            kind,
            version,
            previous_tag,
            exclude_notes,
            output,
        } => {
            let text = read_text(&root.join(CHANGELOG_PATH))?;
            let notes = match kind {
                Kind::Nightly if previous_tag.is_empty() => {
                    format_sections(&parse_sections(&extract_release_block(&text, UNRELEASED)))
                }
                Kind::Nightly => format_sections(&sections_added_since(
                    &git,
                    &previous_tag,
                    &text,
                    excluded_entries_from_notes(&exclude_notes)?,
                )),
                Kind::Stable => {
                    let version = version.strip_prefix('v').unwrap_or(&version);
                    let pattern = format!(
                        r"^## \[{}\](?:\s+-\s+\d{{4}}-\d{{2}}-\d{{2}})?\s*$",
                        regex::escape(version)
                    );
                    let mut block = extract_release_block(&text, &pattern);
                    if block.is_empty() {
                        block = extract_release_block(&text, UNRELEASED);
                    }
                    format_sections(&parse_sections(&block))
                }
            };
            std::fs::write(&output, notes + "\n")?;
            writeln!(out, "Wrote release notes to {output}.")?;
            Ok(0)
        }
        Command::ShouldBuildNightly {
            previous_tag,
            exclude_notes,
            latest_stable_tag,
            exclude_stable_notes,
            head,
        } => {
            let (build, why) = should_build_nightly(
                &git,
                &previous_tag,
                &exclude_notes,
                &latest_stable_tag,
                &exclude_stable_notes,
                &head,
            )?;
            writeln!(out, "should_build={build}")?;
            writeln!(err, "{why}")?;
            Ok(0)
        }
    }
}

fn check(
    git: &Git,
    base: &str,
    head: &str,
    committed_only: bool,
    staged: Option<&str>,
    out: &mut dyn Write,
    err: &mut dyn Write,
) -> Result<u8> {
    let base = git.resolve_base(base)?;
    // Staged, `head` is the index as a tree: diffable, but not a commit to log.
    let (head, message) = match staged {
        Some(_)
            if git
                .run(&["rev-parse", "-q", "--verify", "MERGE_HEAD"])
                .is_ok() =>
        {
            writeln!(
                out,
                "Merge commit; the merged commits are checked on their own."
            )?;
            return Ok(0);
        }
        Some(file) => (git.run(&["write-tree"])?, Some(read_text(Path::new(file))?)),
        None => (head.to_string(), None),
    };
    let head = head.as_str();
    let log_head = if message.is_some() { "HEAD" } else { head };
    let worktree_files = if head == "HEAD" && !committed_only {
        git.worktree_changed_files()?
    } else {
        Vec::new()
    };
    let include_worktree = !worktree_files.is_empty();
    let mut files = output_lines(&git.run(&["diff", "--name-only", &format!("{base}..{head}")])?);
    if include_worktree {
        files = dedupe([files, worktree_files.clone()].concat());
    }
    let mut user_facing = Vec::new();
    for path in &files {
        if git.requires_changelog_entry(path, &base, head, include_worktree)? {
            user_facing.push(path);
        }
    }
    if user_facing.is_empty() {
        writeln!(out, "No user-facing paths changed.")?;
        return Ok(0);
    }

    let mut worktree_user_facing = false;
    for path in &worktree_files {
        worktree_user_facing |=
            git.requires_changelog_entry(path, "HEAD", "HEAD", include_worktree)?;
    }
    let mut messages = git.commit_messages(&base, log_head)?;
    messages.extend(message);
    if !worktree_user_facing && messages_opt_out_of_changelog(&messages) {
        writeln!(
            out,
            "All commits opt out of the changelog gate via a skip marker."
        )?;
        return Ok(0);
    }

    if !files.iter().any(|f| f == CHANGELOG_PATH) {
        writeln!(
            err,
            "User-facing paths changed without updating CHANGELOG.md:"
        )?;
        for path in user_facing {
            writeln!(err, "- {path}")?;
        }
        return Ok(1);
    }

    if git
        .unreleased_added_entries(&base, head, include_worktree)?
        .is_empty()
    {
        writeln!(
            err,
            "CHANGELOG.md changed, but no new bullet was added under ## [Unreleased]."
        )?;
        return Ok(1);
    }

    writeln!(
        out,
        "Found CHANGELOG.md Unreleased entries for user-facing changes."
    )?;
    Ok(0)
}

fn should_build_nightly(
    git: &Git,
    previous_tag: &str,
    exclude_notes: &str,
    latest_stable_tag: &str,
    exclude_stable_notes: &str,
    head: &str,
) -> Result<(bool, &'static str)> {
    if previous_tag.is_empty() {
        return Ok((true, "No previous nightly tag found; building once."));
    }
    if !latest_stable_tag.is_empty() && git.is_ancestor(head, latest_stable_tag) {
        return Ok((false, "Latest stable release already contains this commit."));
    }
    let baseline =
        if !latest_stable_tag.is_empty() && git.is_ancestor(previous_tag, latest_stable_tag) {
            latest_stable_tag
        } else {
            previous_tag
        };
    if messages_request_nightly_build(&git.commit_messages(baseline, head)?) {
        return Ok((true, "Nightly build requested by commit marker."));
    }
    let text = read_text(&git.0.join(CHANGELOG_PATH))?;
    let mut excluded = excluded_entries_from_notes(exclude_notes)?;
    excluded.extend(excluded_entries_from_notes(exclude_stable_notes)?);
    if sections_added_since(git, baseline, &text, excluded).is_empty() {
        Ok((
            false,
            "No new curated changelog entries or nightly build marker found.",
        ))
    } else {
        Ok((
            true,
            "New curated changelog entries found for nightly build.",
        ))
    }
}

/// Git in the repository at the wrapped path.
struct Git<'a>(&'a Path);

impl Git<'_> {
    /// `run_git`: stdout, stripped; a failing command is an error.
    fn run(&self, args: &[&str]) -> Result<String> {
        let output = Process::new("git")
            .arg("-C")
            .arg(self.0)
            .args(args)
            .stderr(Stdio::inherit())
            .output()?;
        if !output.status.success() {
            return Err(format!("git {} failed with {}", args.join(" "), output.status).into());
        }
        Ok(py_strip(&universal_newlines(&String::from_utf8(output.stdout)?)).to_string())
    }

    fn is_ancestor(&self, ancestor: &str, descendant: &str) -> bool {
        Process::new("git")
            .arg("-C")
            .arg(self.0)
            .args(["merge-base", "--is-ancestor", ancestor, descendant])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .is_ok_and(|s| s.success())
    }

    fn resolve_base(&self, base: &str) -> Result<String> {
        if base != "auto" {
            return Ok(base.to_string());
        }
        Ok(if self.run(&["branch", "--show-current"])? == "main" {
            "origin/main"
        } else {
            "origin/dev"
        }
        .to_string())
    }

    fn worktree_changed_files(&self) -> Result<Vec<String>> {
        let tracked = output_lines(&self.run(&["diff", "--name-only", "HEAD"])?);
        let untracked = output_lines(&self.run(&["ls-files", "--others", "--exclude-standard"])?);
        Ok(dedupe([tracked, untracked].concat()))
    }

    fn commit_messages(&self, base: &str, head: &str) -> Result<Vec<String>> {
        let log = self.run(&[
            "log",
            "--no-merges",
            "--format=%H",
            &format!("{base}..{head}"),
        ])?;
        py_splitlines(&log)
            .into_iter()
            .filter(|h| !h.is_empty())
            .map(|commit| self.run(&["show", "-s", "--format=%B", commit]))
            .collect()
    }

    /// `changelog_at`: CHANGELOG.md at `rev`, empty when it doesn't exist there.
    fn changelog_at(&self, rev: &str) -> String {
        self.run(&["show", &format!("{rev}:{CHANGELOG_PATH}")])
            .unwrap_or_default()
    }

    fn requires_changelog_entry(
        &self,
        path: &str,
        base: &str,
        head: &str,
        include_worktree: bool,
    ) -> Result<bool> {
        let normalized = path.replace('\\', "/");
        if normalized != "pyproject.toml" {
            return Ok(is_user_facing_path(&normalized));
        }
        let mut diffs = vec![self.run(&[
            "diff",
            "--unified=0",
            &format!("{base}..{head}"),
            "--",
            "pyproject.toml",
        ])?];
        if include_worktree {
            diffs.push(self.run(&["diff", "--unified=0", "HEAD", "--", "pyproject.toml"])?);
        }
        let changed: Vec<String> = diffs
            .iter()
            .flat_map(|d| changed_lines_from_diff(d))
            .collect();
        Ok(pyproject_changed_lines_require_changelog(&changed))
    }

    /// Curated bullets `head` adds relative to `base`: new Unreleased bullets,
    /// plus every bullet under a release heading `base` doesn't have (cutting
    /// a release is itself the curated changelog update).
    fn unreleased_added_entries(
        &self,
        base: &str,
        head: &str,
        include_worktree: bool,
    ) -> Result<Vec<String>> {
        let base_text = self.changelog_at(base);
        let base_entries: HashSet<String> = unreleased_entries(&base_text).collect();
        let head_text = if include_worktree {
            read_text(&self.0.join(CHANGELOG_PATH))?
        } else {
            self.run(&["show", &format!("{head}:{CHANGELOG_PATH}")])?
        };
        let mut added: Vec<String> = parse_sections(&extract_release_block(&head_text, UNRELEASED))
            .into_iter()
            .flat_map(|s| s.entries)
            .filter(|e| !base_entries.contains(&normalize_entry(e)))
            .collect();
        let base_headings: HashSet<String> = release_headings(&base_text).into_iter().collect();
        for heading in release_headings(&head_text) {
            if base_headings.contains(&heading) {
                continue;
            }
            let block =
                extract_release_block(&head_text, &format!("^{}$", regex::escape(&heading)));
            added.extend(parse_sections(&block).into_iter().flat_map(|s| s.entries));
        }
        Ok(added)
    }
}

fn output_lines(output: &str) -> Vec<String> {
    py_splitlines(output)
        .into_iter()
        .filter(|l| !l.is_empty())
        .map(str::to_string)
        .collect()
}

fn dedupe(items: Vec<String>) -> Vec<String> {
    let mut seen = HashSet::new();
    items
        .into_iter()
        .filter(|i| seen.insert(i.clone()))
        .collect()
}

fn is_user_facing_path(path: &str) -> bool {
    let normalized = path.replace('\\', "/");
    if EXCLUDED_PATH_PREFIXES
        .iter()
        .any(|p| normalized.starts_with(p))
    {
        return false;
    }
    USER_FACING_PATHS.contains(&normalized.as_str())
        || USER_FACING_SUFFIXES.iter().any(|s| normalized.ends_with(s))
        || USER_FACING_PATH_PREFIXES
            .iter()
            .any(|p| normalized.starts_with(p))
}

static REQUIREMENT: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r#"^"([A-Za-z0-9_.-]+)"#).unwrap());

fn pyproject_changed_lines_require_changelog(changed_lines: &[String]) -> bool {
    changed_lines.iter().any(|line| {
        let tooling = REQUIREMENT.captures(line).is_some_and(|c| {
            PYPROJECT_TOOLING_REQUIREMENTS_WITHOUT_CHANGELOG.contains(&casefold(&c[1]).as_str())
        });
        let field = py_strip(line.split('=').next().unwrap_or(""));
        !tooling && !PYPROJECT_METADATA_FIELDS_WITHOUT_CHANGELOG.contains(&field)
    })
}

fn changed_lines_from_diff(diff: &str) -> Vec<String> {
    py_splitlines(diff)
        .into_iter()
        .filter(|l| !(l.starts_with("+++") || l.starts_with("---") || l.starts_with("@@")))
        .filter_map(|l| l.strip_prefix('+').or_else(|| l.strip_prefix('-')))
        .map(|l| py_strip(l).to_string())
        .collect()
}

fn messages_opt_out_of_changelog(messages: &[String]) -> bool {
    !messages.is_empty()
        && messages.iter().all(|m| {
            SKIP_CHANGELOG_MARKERS
                .iter()
                .any(|k| casefold(m).contains(k))
        })
}

fn messages_request_nightly_build(messages: &[String]) -> bool {
    messages.iter().any(|m| {
        NIGHTLY_BUILD_MARKERS
            .iter()
            .any(|k| casefold(m).contains(k))
    })
}

static H2_LINE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?m)^## .*$").unwrap());
static UNRELEASED_HEADING: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)^## \[?Unreleased\]?").unwrap());

/// Every `## ` heading line except Unreleased.
fn release_headings(text: &str) -> Vec<String> {
    H2_LINE
        .find_iter(text)
        .map(|m| m.as_str().to_string())
        .filter(|line| !UNRELEASED_HEADING.is_match(line))
        .collect()
}

static NEXT_H2: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(?m)^## ").unwrap());

/// The text between the first heading matching `heading_pattern` and the
/// next `## ` heading, stripped.
fn extract_release_block(text: &str, heading_pattern: &str) -> String {
    let heading = Regex::new(&format!("(?im){heading_pattern}")).expect("valid heading pattern");
    let Some(m) = heading.find(text) else {
        return String::new();
    };
    let rest = &text[m.end()..];
    let end = NEXT_H2.find(rest).map_or(rest.len(), |n| n.start());
    py_strip(&rest[..end]).to_string()
}

#[derive(Debug)]
struct Section {
    title: String,
    entries: Vec<String>,
}

static SECTION_HEADING: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^#{2,3}\s+(.+?)\s*$").unwrap());
static BULLET: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^-\s+").unwrap());

fn parse_sections(markdown: &str) -> Vec<Section> {
    let mut sections = Vec::new();
    let mut title = String::new();
    let mut entries: Vec<String> = Vec::new();
    let mut entry: Vec<&str> = Vec::new();

    fn flush_entry(entry: &mut Vec<&str>, entries: &mut Vec<String>) {
        if !entry.is_empty() {
            entries.push(py_rstrip(&entry.join("\n")).to_string());
            entry.clear();
        }
    }

    for line in py_splitlines(markdown) {
        if let Some(c) = SECTION_HEADING.captures(line) {
            flush_entry(&mut entry, &mut entries);
            if !title.is_empty() && !entries.is_empty() {
                sections.push(Section {
                    title: title.clone(),
                    entries: std::mem::take(&mut entries),
                });
            }
            entries.clear();
            title = c[1].to_string();
            continue;
        }
        if BULLET.is_match(line) {
            flush_entry(&mut entry, &mut entries);
            entry.push(line);
            continue;
        }
        if !entry.is_empty() && (line.starts_with("  ") || py_strip(line).is_empty()) {
            entry.push(line);
        }
    }
    flush_entry(&mut entry, &mut entries);
    if !title.is_empty() && !entries.is_empty() {
        sections.push(Section { title, entries });
    }
    sections
}

fn format_sections(sections: &[Section]) -> String {
    if sections.is_empty() {
        return "- No user-facing changes".into();
    }
    // Python builds a dict: a repeated title keeps its last section.
    let entries_for = |title: &str| {
        &sections
            .iter()
            .rev()
            .find(|s| s.title == title)
            .expect("title comes from sections")
            .entries
    };
    let mut titles: Vec<&str> = SECTION_ORDER
        .into_iter()
        .filter(|t| sections.iter().any(|s| s.title == *t))
        .collect();
    for section in sections {
        if !titles.contains(&section.title.as_str()) {
            titles.push(&section.title);
        }
    }
    let chunks: Vec<String> = titles
        .iter()
        .map(|title| {
            format!(
                "## {title}\n{}",
                dedupe(entries_for(title).clone()).join("\n")
            )
        })
        .collect();
    py_strip(&chunks.join("\n\n")).to_string()
}

static LINK: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\[([^\]]+)\]\([^)]+\)").unwrap());
static CODE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"`([^`]+)`").unwrap());
static BOLD: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\*\*([^*]+)\*\*").unwrap());
static BOLD_UNDERSCORE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"__([^_]+)__").unwrap());
static ITALIC: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\*([^*]+)\*").unwrap());
static ITALIC_UNDERSCORE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"_([^_]+)_").unwrap());
static LEADING_BULLET: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^[-*+]\s+").unwrap());
static DASH: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\s+[-\u{2013}\u{2014}]\s+").unwrap());
static SPACES: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\s+").unwrap());

/// An entry with its markdown and whitespace flattened, for comparing
/// entries across wording-neutral edits.
fn normalize_entry(entry: &str) -> String {
    let mut e = entry.to_string();
    for re in [
        &LINK,
        &CODE,
        &BOLD,
        &BOLD_UNDERSCORE,
        &ITALIC,
        &ITALIC_UNDERSCORE,
    ] {
        e = re.replace_all(&e, "${1}").into_owned();
    }
    let e = LEADING_BULLET.replace(py_strip(&e), "").into_owned();
    let e = DASH.replace_all(&e, " - ");
    let e = SPACES.replace_all(&e, " ");
    py_strip(&casefold(&e)).to_string()
}

fn unreleased_entries(text: &str) -> impl Iterator<Item = String> {
    parse_sections(&extract_release_block(text, UNRELEASED))
        .into_iter()
        .flat_map(|s| s.entries)
        .map(|e| normalize_entry(&e))
}

fn sections_added_since(
    git: &Git,
    base_ref: &str,
    head_text: &str,
    mut excluded: HashSet<String>,
) -> Vec<Section> {
    excluded.extend(unreleased_entries(&git.changelog_at(base_ref)));
    parse_sections(&extract_release_block(head_text, UNRELEASED))
        .into_iter()
        .filter_map(|s| {
            let entries: Vec<String> = s
                .entries
                .into_iter()
                .filter(|e| !excluded.contains(&normalize_entry(e)))
                .collect();
            (!entries.is_empty()).then_some(Section {
                title: s.title,
                entries,
            })
        })
        .collect()
}

/// Normalized entries of a previous release's notes (missing file: none).
fn excluded_entries_from_notes(path: &str) -> Result<HashSet<String>> {
    if path.is_empty() || !Path::new(path).exists() {
        return Ok(HashSet::new());
    }
    let text = read_text(Path::new(path))?;
    Ok(parse_sections(&text)
        .into_iter()
        .flat_map(|s| s.entries)
        .map(|e| normalize_entry(&e))
        .collect())
}

/// A file read the way Python's text mode reads it: `\r\n` and `\r` become `\n`.
fn read_text(path: &Path) -> Result<String> {
    Ok(universal_newlines(&std::fs::read_to_string(path)?))
}

fn universal_newlines(s: &str) -> String {
    s.replace("\r\n", "\n").replace('\r', "\n")
}

/// Python's `str.isspace` for one character.
fn py_space(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

fn py_strip(s: &str) -> &str {
    s.trim_matches(py_space)
}

fn py_rstrip(s: &str) -> &str {
    s.trim_end_matches(py_space)
}

/// Python's `str.splitlines()`.
fn py_splitlines(s: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut chars = s.char_indices().peekable();
    while let Some((i, c)) = chars.next() {
        if matches!(
            c,
            '\n' | '\r'
                | '\u{b}'
                | '\u{c}'
                | '\u{1c}'
                | '\u{1d}'
                | '\u{1e}'
                | '\u{85}'
                | '\u{2028}'
                | '\u{2029}'
        ) {
            lines.push(&s[start..i]);
            start = i + c.len_utf8();
            if c == '\r' && chars.peek().is_some_and(|&(_, n)| n == '\n') {
                chars.next();
                start += 1;
            }
        }
    }
    if start < s.len() {
        lines.push(&s[start..]);
    }
    lines
}

/// Python's `str.casefold()` for the characters where it differs from
/// lowercasing.
fn casefold(s: &str) -> String {
    s.to_lowercase().replace('ß', "ss").replace('ς', "σ")
}

#[cfg(test)]
mod tests {
    //! Golden parity with `scripts/changelog_tools.py`, recorded by
    //! `rust/tools/golden/changelog.py`: every scenario builds the same git
    //! repository and runs the same command line.

    use clap::Parser;
    use serde_json::Value;

    use super::*;

    #[derive(Parser)]
    struct Cli {
        #[command(subcommand)]
        cmd: Command,
    }

    fn git(dir: &Path, args: &[&str]) {
        let status = Process::new("git")
            .arg("-C")
            .arg(dir)
            .args(args)
            .env("GIT_AUTHOR_DATE", "2026-01-01T00:00:00Z")
            .env("GIT_COMMITTER_DATE", "2026-01-01T00:00:00Z")
            .stdout(Stdio::null())
            .status()
            .unwrap();
        assert!(status.success(), "git {args:?}");
    }

    /// Write `files`; the marker stands for the recorded real changelog.
    fn write_files(dir: &Path, files: &Value, real: &str) {
        for (path, content) in files.as_object().into_iter().flatten() {
            let path = dir.join(path);
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            let content = content.as_str().unwrap();
            let content = if content == "@real-changelog" {
                real
            } else {
                content
            };
            std::fs::write(path, content).unwrap();
        }
    }

    fn build_repo(dir: &Path, scenario: &Value, real: &str) {
        git(dir, &["init", "-q", "-b", "main"]);
        for (k, v) in [
            ("user.name", "Golden"),
            ("user.email", "golden@example.com"),
            ("commit.gpgsign", "false"),
            ("tag.gpgsign", "false"),
            ("core.autocrlf", "false"),
        ] {
            git(dir, &["config", k, v]);
        }
        for step in scenario["steps"].as_array().unwrap() {
            write_files(dir, &step["write"], real);
            for path in step["delete"].as_array().into_iter().flatten() {
                std::fs::remove_file(dir.join(path.as_str().unwrap())).unwrap();
            }
            if let Some(branch) = step["branch"].as_str() {
                git(dir, &["checkout", "-q", "-B", branch]);
            }
            if let Some(message) = step["commit"].as_str() {
                git(dir, &["add", "-A"]);
                git(dir, &["commit", "-q", "--allow-empty", "-m", message]);
            }
            if let Some(tag) = step["tag"].as_str() {
                git(dir, &["tag", tag]);
            }
            for (name, target) in step["refs"].as_object().into_iter().flatten() {
                git(dir, &["update-ref", name, target.as_str().unwrap()]);
            }
        }
        write_files(dir, &scenario["worktree"], real);
    }

    #[test]
    fn matches_python_changelog_tools() {
        let path = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../testdata/golden/changelog/scenarios.json");
        let golden: Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        let real = golden["real_changelog"].as_str().unwrap();
        for scenario in golden["scenarios"].as_array().unwrap() {
            let name = scenario["name"].as_str().unwrap();
            let repo = tempfile::tempdir().unwrap();
            let aux = tempfile::tempdir().unwrap();
            build_repo(repo.path(), scenario, real);
            write_files(aux.path(), &scenario["aux"], real);
            let aux_dir = aux.path().to_str().unwrap();
            let args: Vec<String> = std::iter::once("changelog".to_string())
                .chain(
                    scenario["args"]
                        .as_array()
                        .unwrap()
                        .iter()
                        .map(|a| a.as_str().unwrap().replace("{aux}", aux_dir)),
                )
                .collect();
            let cmd = Cli::try_parse_from(&args).unwrap().cmd;
            let (mut out, mut err) = (Vec::new(), Vec::new());
            let code = run(repo.path(), cmd, &mut out, &mut err).unwrap();
            let expected = &scenario["expected"];
            let text = |b: Vec<u8>| String::from_utf8(b).unwrap().replace(aux_dir, "{aux}");
            assert_eq!(code as u64, expected["code"].as_u64().unwrap(), "{name}");
            assert_eq!(text(out), expected["stdout"].as_str().unwrap(), "{name}");
            assert_eq!(text(err), expected["stderr"].as_str().unwrap(), "{name}");
            if let Some(notes) = expected["output"].as_str() {
                let written = std::fs::read_to_string(aux.path().join("notes.md")).unwrap();
                assert_eq!(written, notes, "{name}");
            }
        }
    }

    #[test]
    fn staged_check_covers_the_commit_being_made() {
        let repo = tempfile::tempdir().unwrap();
        let dir = repo.path();
        let init = serde_json::json!({"steps": [{
            "write": {"CHANGELOG.md": "# Changelog

## [Unreleased]
"},
            "commit": "init",
        }]});
        build_repo(dir, &init, "");
        let msg = dir.join(".git/COMMIT_EDITMSG");
        let check = |message: &str| {
            std::fs::write(&msg, message).unwrap();
            let args = ["changelog", "check", "--base", "HEAD", "--staged"];
            let cmd = Cli::try_parse_from(args.into_iter().chain([msg.to_str().unwrap()]))
                .unwrap()
                .cmd;
            run(dir, cmd, &mut Vec::new(), &mut Vec::new()).unwrap()
        };

        std::fs::create_dir_all(dir.join("rust/crates")).unwrap();
        std::fs::write(
            dir.join("rust/crates/app.rs"),
            "fn main() {}
",
        )
        .unwrap();
        assert_eq!(
            check("fix: thing"),
            0,
            "unstaged changes aren't in the commit"
        );
        git(dir, &["add", "-A"]);
        assert_eq!(check("fix: thing"), 1, "user-facing without a bullet");
        assert_eq!(
            check(
                "refactor: thing

Changelog: none"
            ),
            0,
            "opted out"
        );

        let bullet = "# Changelog

## [Unreleased]

### Fixed

- The thing works.
";
        std::fs::write(dir.join("CHANGELOG.md"), bullet).unwrap();
        git(dir, &["add", "-A"]);
        assert_eq!(check("fix: thing"), 0, "bullet staged");
    }

    #[test]
    fn rust_edition_paths_are_user_facing() {
        assert!(is_user_facing_path("rust/crates/aw-app/src/main.rs"));
        assert!(is_user_facing_path(r"rust\packaging\macos\Info.plist"));
        assert!(!is_user_facing_path("rust/tools/golden/changelog.py"));
        assert!(!is_user_facing_path(
            "src/accessiweather/weather_gov_api_client/x.py"
        ));
    }
}
