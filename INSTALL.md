# Installing AccessiWeather

## Prebuilt packages

Download from https://orinks.net/accessiweather or the [GitHub releases](https://github.com/Orinks/AccessiWeather/releases) page.

## From source

The maintained build path is the Rust edition:

```bash
cd rust
cargo build --release -p accessiweather
./target/release/accessiweather
```

Packaging: `cargo xtask package`. Details: [rust/README.md](rust/README.md).

Contributor setup: [CONTRIBUTING.md](CONTRIBUTING.md).
