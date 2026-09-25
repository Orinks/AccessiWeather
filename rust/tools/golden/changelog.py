"""
Golden outputs for `cargo xtask changelog` from `scripts/changelog_tools.py`.

Every scenario builds a small git repository, runs the Python tool's command
line in it and records exit code, stdout, stderr and the written notes. The
Rust test (`rust/xtask/src/changelog.rs`) rebuilds the same repository and
runs the same command line.

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/changelog.py
Writes rust/testdata/golden/changelog/scenarios.json.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RUST = Path(__file__).resolve().parents[2]
ROOT = RUST.parent
TOOL = ROOT / "scripts" / "changelog_tools.py"
OUT = RUST / "testdata" / "golden" / "changelog" / "scenarios.json"
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z",
}

REAL = (ROOT / "CHANGELOG.md").read_bytes().decode("utf-8")
# Scenarios name the real changelog by this marker; the golden file stores
# its text once.
REAL_MARKER = "@real-changelog"

BASE = """# Changelog

## [Unreleased]

### Added
- First feature
- Second feature with `code` and **bold**

### Fixed
- A bug fix
  that continues on the next line

## [0.1.0] - 2026-01-01

### Added
- Initial release
"""

# Adds entries, rewords one only in markdown/case/whitespace (still the same
# entry), and drops another.
NEXT = """# Changelog

## [Unreleased]

### Added
- first   FEATURE
- Brand new thing – with an en dash
- See [the docs](https://example.com/docs) for __details__

### Fixed
- A bug fix
  that continues on the next line
- Another fix with *emphasis* and _underscores_

## [0.1.0] - 2026-01-01

### Added
- Initial release
"""

EDGE = """# Changelog

## Unreleased

### Fixed
- Fixed first, listed before Added
- Duplicate entry
- Duplicate entry

### Accessibility
- Screen reader label added

### Added
- Added entry one
* Starred line is not a bullet
#### Deep heading is not a section
- Added entry two

  - Indented continuation after a blank line
trailing text that is ignored

### Added
- Second Added section wins

### Notes
### Empty section above

## [2.0.0] - 2026-05-05

### Changed
- Two point oh change

## [1.9.0]

### Fixed
- Undated release with trailing spaces

## [1.8.0] - 2026-04-04 [YANKED]

### Removed
- Yanked release
"""

EMPTY_UNRELEASED = """# Changelog

## [Unreleased]

## [0.1.0] - 2026-01-01

### Added
- Initial release
"""

RELEASED = BASE.replace(
    "## [Unreleased]\n",
    "## [Unreleased]\n\n## [0.2.0] - 2026-02-01\n",
)

PYPROJECT = """[project]
name = "accessiweather"
version = "0.1.0"
description = "Weather"
dependencies = [
    "httpx>=0.28",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.16.0",
]
"""


def step(write=None, commit=None, tag=None, delete=None, branch=None, refs=None) -> dict:
    s = {"write": write or {}}
    if commit is not None:
        s["commit"] = commit
    if tag:
        s["tag"] = tag
    if delete:
        s["delete"] = delete
    if branch:
        s["branch"] = branch
    if refs:
        s["refs"] = refs
    return s


def scenario(name, steps, args, worktree=None, aux=None) -> dict:
    return {
        "name": name,
        "steps": steps,
        "worktree": worktree or {},
        "aux": aux or {},
        "args": args,
    }


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, env=GIT_ENV, stdout=subprocess.DEVNULL
    )


def write_files(base: Path, files: dict) -> None:
    for rel, content in files.items():
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((REAL if content == REAL_MARKER else content).encode("utf-8"))


def build_repo(repo: Path, sc: dict) -> None:
    git(repo, "init", "-q", "-b", "main")
    for key, value in [
        ("user.name", "Golden"),
        ("user.email", "golden@example.com"),
        ("commit.gpgsign", "false"),
        ("tag.gpgsign", "false"),
        ("core.autocrlf", "false"),
    ]:
        git(repo, "config", key, value)
    for s in sc["steps"]:
        write_files(repo, s["write"])
        for rel in s.get("delete", []):
            (repo / rel).unlink()
        if "branch" in s:
            git(repo, "checkout", "-q", "-B", s["branch"])
        if "commit" in s:
            git(repo, "add", "-A")
            git(repo, "commit", "-q", "--allow-empty", "-m", s["commit"])
        if "tag" in s:
            git(repo, "tag", s["tag"])
        for name, target in s.get("refs", {}).items():
            git(repo, "update-ref", name, target)
    write_files(repo, sc["worktree"])


def record(sc: dict) -> dict:
    with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as aux_dir:
        repo, aux = Path(repo_dir), Path(aux_dir)
        build_repo(repo, sc)
        write_files(aux, sc["aux"])
        args = [a.replace("{aux}", aux_dir) for a in sc["args"]]
        proc = subprocess.run(
            [sys.executable, str(TOOL), *args],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        # Git's own "fatal:" lines (a ref without CHANGELOG.md) reach stderr
        # through the inherited handle; the Rust port leaves them on the
        # console rather than in its output.
        stderr = "".join(
            line for line in proc.stderr.splitlines(keepends=True) if not line.startswith("fatal: ")
        )
        if "Traceback" in stderr:
            raise SystemExit(f"{sc['name']} crashed:\n{stderr}")
        notes = aux / "notes.md"
        return {
            **sc,
            "expected": {
                "code": proc.returncode,
                "stdout": proc.stdout.replace(aux_dir, "{aux}"),
                "stderr": stderr.replace(aux_dir, "{aux}"),
                "output": notes.read_text(encoding="utf-8") if notes.exists() else None,
            },
        }


def notes_scenarios() -> list[dict]:
    out = []
    notes = ["--output", "{aux}/notes.md"]
    one = [step({"CHANGELOG.md": REAL_MARKER}, "real changelog")]
    versions = re.findall(r"^## \[([^\]]+)\]", REAL, re.MULTILINE)
    for version in [v for v in versions if v.lower() != "unreleased"] + ["9.9.9"]:
        out.append(
            scenario(
                f"real stable v{version}",
                one,
                ["notes", "--kind", "stable", "--version", f"v{version}", *notes],
            )
        )
    out.append(scenario("real nightly", one, ["notes", "--kind", "nightly", *notes]))

    edge = [step({"CHANGELOG.md": EDGE}, "edge")]
    for version in ["2.0.0", "v1.9.0", "1.8.0", "vv2.0.0", ""]:
        out.append(
            scenario(
                f"edge stable {version!r}",
                edge,
                ["notes", "--kind", "stable", "--version", version, *notes],
            )
        )
    out.append(scenario("edge nightly", edge, ["notes", "--kind", "nightly", *notes]))
    crlf = [step({"CHANGELOG.md": EDGE.replace("\n", "\r\n")}, "crlf")]
    out.append(scenario("crlf nightly", crlf, ["notes", "--kind", "nightly", *notes]))
    out.append(
        scenario(
            "crlf stable",
            crlf,
            ["notes", "--kind", "stable", "--version", "2.0.0", *notes],
        )
    )
    empty = [step({"CHANGELOG.md": EMPTY_UNRELEASED}, "empty")]
    out.append(scenario("empty unreleased nightly", empty, ["notes", "--kind", "nightly", *notes]))
    out.append(
        scenario(
            "empty unreleased stable fallback",
            empty,
            ["notes", "--kind", "stable", "--version", "0.2.0", *notes],
        )
    )

    history = [
        step({"CHANGELOG.md": BASE}, "base", tag="nightly-20260101"),
        step({"CHANGELOG.md": NEXT, "src/app.py": "x = 1\n"}, "next"),
    ]
    prev = ["--previous-tag", "nightly-20260101"]
    out.append(
        scenario("nightly since tag", history, ["notes", "--kind", "nightly", *prev, *notes])
    )
    out.append(
        scenario(
            "nightly since tag excluding previous notes",
            history,
            [
                "notes",
                "--kind",
                "nightly",
                *prev,
                "--exclude-notes",
                "{aux}/prev.md",
                *notes,
            ],
            aux={"prev.md": "## Fixed\n- ANOTHER fix with emphasis and underscores\n"},
        )
    )
    out.append(
        scenario(
            "nightly since tag with missing exclude file",
            history,
            [
                "notes",
                "--kind",
                "nightly",
                *prev,
                "--exclude-notes",
                "{aux}/missing.md",
                *notes,
            ],
        )
    )
    no_changelog_at_tag = [
        step({"README.md": "hi\n"}, "readme", tag="nightly-20260101"),
        step({"CHANGELOG.md": NEXT}, "changelog"),
    ]
    out.append(
        scenario(
            "nightly since tag without a changelog",
            no_changelog_at_tag,
            ["notes", "--kind", "nightly", *prev, *notes],
        )
    )
    return out


def should_build_scenarios() -> list[dict]:
    cmd = ["should-build-nightly"]
    prev = ["--previous-tag", "nightly-20260101"]
    base = step({"CHANGELOG.md": BASE}, "base", tag="nightly-20260101")
    out = [
        scenario("no previous nightly", [base], cmd),
        scenario(
            "nothing new",
            [base, step({"src/app.py": "x = 1\n"}, "internal change")],
            [*cmd, *prev],
        ),
        scenario(
            "new curated entry",
            [base, step({"CHANGELOG.md": NEXT}, "feat: things")],
            [*cmd, *prev],
        ),
        scenario(
            "nightly marker",
            [base, step({"src/app.py": "x = 2\n"}, "fix: packaged thing\n\nNightly: build")],
            [*cmd, *prev],
        ),
        scenario(
            "bracket marker any case",
            [base, step({"src/app.py": "x = 3\n"}, "fix: thing [Nightly Build]")],
            [*cmd, *prev],
        ),
        scenario(
            "stable release contains head",
            [base, step({"CHANGELOG.md": NEXT}, "feat", tag="v0.2.0")],
            [*cmd, *prev, "--latest-stable-tag", "v0.2.0"],
        ),
        scenario(
            "baseline moves to stable",
            [
                base,
                step({"CHANGELOG.md": NEXT}, "feat", tag="v0.2.0"),
                step({"src/app.py": "x = 4\n"}, "internal"),
            ],
            [*cmd, *prev, "--latest-stable-tag", "v0.2.0"],
        ),
        scenario(
            "new entry after stable",
            [
                base,
                step({"CHANGELOG.md": BASE}, "noop", tag="v0.2.0"),
                step({"CHANGELOG.md": NEXT}, "feat"),
            ],
            [*cmd, *prev, "--latest-stable-tag", "v0.2.0"],
        ),
        scenario(
            "stable not descended from nightly",
            [
                step({"CHANGELOG.md": BASE}, "root", tag="v0.1.0"),
                step({"CHANGELOG.md": BASE, "a.txt": "a\n"}, "nightly", tag="nightly-20260101"),
                step({"CHANGELOG.md": NEXT}, "feat"),
            ],
            [*cmd, *prev, "--latest-stable-tag", "v0.1.0"],
        ),
        scenario(
            "entries already in previous nightly notes",
            [base, step({"CHANGELOG.md": NEXT}, "feat")],
            [*cmd, *prev, "--exclude-notes", "{aux}/prev.md"],
            aux={
                "prev.md": "## Added\n- Brand new thing - with an en dash\n"
                "- See the docs for details\n\n## Fixed\n"
                "- Another fix with emphasis and underscores\n"
            },
        ),
        scenario(
            "entries already in stable notes",
            [base, step({"CHANGELOG.md": NEXT}, "feat")],
            [*cmd, *prev, "--exclude-stable-notes", "{aux}/stable.md"],
            aux={
                "stable.md": "## Added\n- Brand new thing – with an en dash\n"
                "- See [the docs](x) for details\n\n## Fixed\n"
                "- Another fix with *emphasis* and _underscores_\n"
            },
        ),
    ]
    return out


def check_scenarios() -> list[dict]:
    base = step({"CHANGELOG.md": BASE, "pyproject.toml": PYPROJECT, "src/app.py": "x = 0\n"}, "base", tag="base")
    check = ["check", "--base", "base"]
    return [
        scenario("docs only", [base, step({"docs/a.md": "a\n"}, "docs")], check),
        scenario("source without changelog", [base, step({"src/app.py": "x = 1\n", "src/b.py": "b\n"}, "feat")], check),
        scenario(
            "source with new bullet",
            [base, step({"src/app.py": "x = 1\n", "CHANGELOG.md": NEXT}, "feat")],
            check,
        ),
        scenario(
            "changelog reworded only",
            [
                base,
                step(
                    {
                        "src/app.py": "x = 1\n",
                        "CHANGELOG.md": BASE.replace("- First feature", "- **First** feature"),
                    },
                    "feat",
                ),
            ],
            check,
        ),
        scenario(
            "all commits opt out",
            [
                base,
                step({"src/app.py": "x = 1\n"}, "refactor: a\n\nChangelog: none"),
                step({"src/app.py": "x = 2\n"}, "refactor: b [skip changelog]"),
            ],
            check,
        ),
        scenario(
            "one commit opts out",
            [
                base,
                step({"src/app.py": "x = 1\n"}, "refactor: a\n\nChangelog: none"),
                step({"src/app.py": "x = 2\n"}, "feat: b"),
            ],
            check,
        ),
        scenario(
            "pyproject version bump",
            [base, step({"pyproject.toml": PYPROJECT.replace('"0.1.0"', '"0.2.0"')}, "bump")],
            check,
        ),
        scenario(
            "pyproject ruff bump",
            [base, step({"pyproject.toml": PYPROJECT.replace("ruff>=0.16.0", "ruff>=0.16.1")}, "ruff")],
            check,
        ),
        scenario(
            "pyproject new dependency",
            [
                base,
                step(
                    {"pyproject.toml": PYPROJECT.replace('"httpx>=0.28",', '"httpx>=0.28",\n    "rich>=13",')},
                    "deps",
                ),
            ],
            check,
        ),
        scenario(
            "release cut",
            [base, step({"src/app.py": "x = 1\n", "CHANGELOG.md": RELEASED}, "release 0.2.0")],
            check,
        ),
        scenario(
            "generated client only",
            [base, step({"src/accessiweather/weather_gov_api_client/models.py": "m\n"}, "regen")],
            check,
        ),
        scenario(
            "installer and spec files",
            [base, step({"installer/x.iss": "i\n", "tools/app.spec": "s\n"}, "build")],
            check,
        ),
        scenario(
            "dirty worktree without changelog",
            [base],
            ["check", "--base", "base"],
            worktree={"src/app.py": "x = 9\n", "src/new.py": "n\n"},
        ),
        scenario(
            "dirty worktree with changelog",
            [base],
            ["check", "--base", "base"],
            worktree={"src/app.py": "x = 9\n", "CHANGELOG.md": NEXT},
        ),
        scenario(
            "committed only ignores worktree",
            [base, step({"docs/a.md": "a\n"}, "docs")],
            ["check", "--base", "base", "--committed-only"],
            worktree={"src/app.py": "x = 9\n"},
        ),
        scenario(
            "worktree change defeats opt-out",
            [base, step({"src/app.py": "x = 1\n"}, "refactor\n\nChangelog: none")],
            ["check", "--base", "base"],
            worktree={"src/other.py": "o\n"},
        ),
        scenario(
            "explicit head skips worktree",
            [base, step({"src/app.py": "x = 1\n", "CHANGELOG.md": NEXT}, "feat", tag="tip")],
            ["check", "--base", "base", "--head", "tip"],
            worktree={"src/app.py": "x = 9\n"},
        ),
        scenario(
            "auto base on a feature branch",
            [
                base,
                step(refs={"refs/remotes/origin/dev": "base"}, branch="feature"),
                step({"src/app.py": "x = 1\n"}, "feat"),
            ],
            ["check", "--base", "auto"],
        ),
    ]


def main() -> None:
    results = [record(sc) for sc in [*notes_scenarios(), *should_build_scenarios(), *check_scenarios()]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    golden = {"real_changelog": REAL, "scenarios": results}
    OUT.write_text(json.dumps(golden, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", OUT, len(results), "scenarios")


if __name__ == "__main__":
    main()
