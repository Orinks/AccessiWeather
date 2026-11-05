# Contributing to AccessiWeather

Thank you for your interest in contributing to AccessiWeather.

## Code of Conduct

Please be respectful and considerate when interacting with other contributors. We aim to foster an inclusive and welcoming community.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Work in the Rust edition under `rust/` (see [rust/README.md](rust/README.md))
4. Create a branch from `dev`:
   ```
   git checkout dev
   git pull
   git checkout -b feature/your-feature-name
   ```

## Development process

The ship and test path is Rust only:

```bash
cd rust
cargo fmt --all -- --check
cargo clippy --workspace --all-targets
cargo test --workspace
cargo build -p accessiweather
./target/debug/accessiweather --check
```

Packaging and release tooling live in `cargo xtask` (see [rust/README.md](rust/README.md)).

Pull requests normally target `dev`. `rust.yml` validates formatting, Clippy, tests, the headless `--check`, and a windowed `--smoke` on Linux, Windows, and macOS.

## Accessibility

All UI components must stay accessible to screen readers. Before submitting a pull request that includes UI changes:

1. Ensure controls have appropriate labels and descriptions
2. Test keyboard navigation for new features
3. Verify screen readers can announce new UI
4. Follow [docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md)

## Changelog

User-facing changes need a curated `CHANGELOG.md` bullet under `## [Unreleased]`. Internal-only work can use the `skip-changelog` PR label or `Changelog: none` / `[skip changelog]` in the commit message. See [.github/workflows/README.md](.github/workflows/README.md).

## Style

- Conventional commits and conventional PR titles
- No agent or staff names in commit subjects or bodies
- Prefer `git --no-pager` for inspection commands on Windows

## Feature requests and bug reports

Use the GitHub issue tracker. For bugs, include steps to reproduce, expected vs actual behavior, and your OS.
