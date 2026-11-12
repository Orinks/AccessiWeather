<!-- This file mirrors AGENTS.md plus the writing rules below. Edit AGENTS.md for shared guidance. -->

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

---

## Writing rule: no accessibility or audio marketing talk

This applies to everything you write: READMEs, store and site descriptions,
release notes, changelogs, forum posts (audiogames.net and similar), commit
messages, PR text, and docs.

- Never describe a game or app as audio-first, blind-first, accessibility-first,
  truly accessible, designed with accessibility at the forefront, crafted for
  keyboard and screen reader use, specifically optimized for screen reader
  users, or anything that means the same thing.
- Exception for games: a game may say once, plainly, that it is an audio game
  for blind and visually impaired players (for example "An audio trucking game
  for blind and visually impaired players."). Say it one time, in the opening
  description, and nothing beyond that.
- Skip audio puffery too: "rich and immersive soundscapes", "a game designed to
  be heard", "sounds like you're really there", "your eyes don't matter, only
  your ears do", and the like.
- Why: the audience already takes accessibility and audio for granted. Saying
  so is filler. Describe what the thing actually does instead: its features,
  content, controls, and what changed.
- Facts are fine when they are specific and useful, for example "works with
  NVDA and JAWS" in a requirements list or a note about which keys open a menu.



---

## Changelog Maintenance

Keep `CHANGELOG.md` updated with user-facing changes. Add the bullet in the same commit as the
change: a `commit-msg` hook (`pre-commit install`) rejects a user-facing commit without one, unless
the message carries `Changelog: none` for internal work.

### When to Add

- User-visible features, fixes, or changes
- UI, behavior, performance, appearance changes

### What to Skip

- Internal refactoring, CI/CD improvements
- Test-only changes, documentation updates
- Developer-facing changes

### Writing Style

Write like a human, not a chatbot:

```markdown
# DON'T
- Performance improvements have been implemented via cache-first design

# DO
- Performance boost: Now serves cached results instantly while refreshing
  in the background - 80%+ fewer API calls
```

**Avoid**: Passive voice, hedging language, generic terms ("enhanced", "optimized")
**Use**: Contractions, direct address ("You can now..."), specific benefits

**Length**: one sentence per change, under 25 words; the root cause, the mechanism and
the before-and-after story go in the commit or PR, not the bullet. The full recipe is
the `writing-changelog-entries` skill in `.claude/skills/`.
