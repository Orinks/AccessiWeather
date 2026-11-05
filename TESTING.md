# Testing Guide for AccessiWeather

AccessiWeather's maintained test path is the Rust workspace under `rust/`. There is no pytest matrix and no `pip install` gate.

## Quick reference

```bash
cd rust

# Format, lint, and unit/integration tests used on pull requests
cargo fmt --all -- --check
cargo clippy --workspace --all-targets
cargo test --workspace

# Headless replay of recorded responses (same as CI's --check)
cargo build -p accessiweather
./target/debug/accessiweather --check

# Window smoke (CI uses Xvfb on Linux)
./target/debug/accessiweather --smoke
```

## Live provider tests

Scheduled live NWS / Open-Meteo / IEM coverage runs in `.github/workflows/rust-integration.yml`:

```bash
cd rust
cargo test -p aw-providers --test live -- --ignored
```

## Golden data

Recorded golden fixtures live under `rust/testdata/golden/`. Regenerators are Python helpers in `rust/tools/golden/` that compare against the legacy Python reference tree in `src/accessiweather/` when you still have a historical checkout that can run it. Day-to-day development does not require regenerating them.

## CI

| Workflow | Purpose |
|----------|---------|
| `rust.yml` | PR / `dev` push: fmt, clippy, tests, `--check`, `--smoke` |
| `rust-build.yml` | Nightly and tagged packaging via `cargo xtask package` |
| `rust-integration.yml` | Scheduled live provider tests |

See [.github/workflows/README.md](.github/workflows/README.md).
