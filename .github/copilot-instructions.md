# AccessiWeather agent notes

- Maintained edition: `rust/` (Cargo). Do not add pytest, pip, or Nuitka gates.
- PRs target `dev`. Validation is `.github/workflows/rust.yml`.
- Packaging / release: `cargo xtask` (see `rust/README.md`).
- `src/accessiweather/` is a legacy Python reference for golden regenerators only.
- Leave `ios/` and `push-server/` alone unless the task names them.
- Conventional commits; no agent names in commit messages.
- User-facing changes need a `CHANGELOG.md` Unreleased bullet (or skip markers).
