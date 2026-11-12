# AI Agent Guidelines - AccessiWeather

**Role:** You are working on AccessiWeather's native Rust desktop edition under `rust/`. The ship and test path is Cargo only — no pytest matrix and no `pip install` gates.

---

## Quick reference

```bash
cd rust
cargo fmt --all -- --check
cargo clippy --workspace --all-targets
cargo test --workspace
cargo build -p accessiweather
./target/debug/accessiweather --check
./target/debug/accessiweather --smoke
cargo xtask package          # release packaging
cargo xtask changelog check  # CHANGELOG gate
```

See [rust/README.md](rust/README.md) for crates, packaging, and release flow.

---

## Project overview

AccessiWeather is a cross-platform accessible desktop weather application. The maintained edition uses wxDragon (wxWidgets) with prism/prismer for screen reader announcements.

| Area | Location |
|------|----------|
| Domain / fusion / presenter | `rust/crates/aw-core` |
| Weather providers | `rust/crates/aw-providers` |
| Config / keys / portable | `rust/crates/aw-store` |
| Sound packs | `rust/crates/aw-audio` + `soundpacks/` |
| NOAA Weather Radio | `rust/crates/aw-radio` |
| AI / Assistant | `rust/crates/aw-ai` |
| Notifications | `rust/crates/aw-notify` |
| App binary / UI | `rust/crates/aw-app` |
| Packaging / release | `rust/xtask` |

The former Python edition (`src/accessiweather/`, `rust/tools/golden/`) has been removed. Its recorded output lives on as golden fixtures in `rust/testdata/golden/`; the source is in git history if you need it.

`ios/` and `push-server/` are separate surfaces; leave them alone unless the task names them.

---

## Git workflow

- Branch from `dev`; open PRs into `dev`
- Conventional commits; no agent or staff names in subjects or bodies
- User-facing changes need a `CHANGELOG.md` Unreleased bullet (or `skip-changelog` / `Changelog: none`)

---

## CI

| Workflow | Purpose |
|----------|---------|
| `rust.yml` | PR / `dev` push validation |
| `rust-build.yml` | Nightly and tagged releases |
| `rust-integration.yml` | Scheduled live provider tests |

---

## Accessibility

- Keyboard access for every interactive control
- Clear accessible names and useful descriptions
- Intentional initial focus in dialogs
