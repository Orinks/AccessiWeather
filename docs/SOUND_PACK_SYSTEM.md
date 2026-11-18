# Sound Pack System

The Rust sound implementation is in
[`rust/crates/aw-audio`](../rust/crates/aw-audio/src/lib.rs).
For selecting or creating packs, see [Sound Packs](SOUND_PACKS.md).

## Components

| Module | Responsibility |
|--------|----------------|
| `aw_audio::pack` | Directory resolution, metadata, validation, event lookup |
| `aw_audio::player` | Playback and preview control |
| `aw_audio::alert_sounds` | Ordered alert event candidates |
| `aw_audio::manager` | Manager and creation-wizard operations |
| `aw_audio::installer` | ZIP extraction and installation |
| `aw_audio::community`, `aw_audio::submission` | Community listing and sharing |

The desktop dialogs are
[`soundpack_manager.rs`](../rust/crates/aw-app/src/ui/soundpack_manager.rs)
and [`soundpack_wizard.rs`](../rust/crates/aw-app/src/ui/soundpack_wizard.rs).
Settings wiring lives in `settings_dialog.rs` and `settings_tabs.rs`
in the same UI directory.

## Storage

`aw_audio::soundpacks_dir()` resolves the directory for the current run:

- Portable runs prefer `data/soundpacks` beside the executable when present;
  they can also use a bundled `soundpacks` folder.
- Installed packages use `soundpacks` beside the executable, or
  `Contents/Resources/soundpacks` in a macOS app bundle.
- Development builds fall back to the repository's `soundpacks` directory.

`cargo xtask package` bundles `soundpacks/default`. The Windows portable ZIP
also includes `data/soundpacks/default`.

## Playing application events

The process-wide `aw_audio::player()` returns a `SoundPlayer`. Callers check
the global sound setting before requesting event playback:

```rust
let settings = aw_core::settings::AppSettings::default();
if settings.sound_enabled {
    aw_audio::player().play_event(
        &settings.sound_pack,
        "startup",
        &settings.muted_sound_events,
    );
}
```

`play_event` skips muted events. `resolve_event` returns the file and volume
without playing it. `play_sample` previews a pack's sample; the manager uses
`preview_play`, `preview_stop`, and `preview_is_playing` for its preview controls.

For alerts, `alert_sounds::get_candidate_sound_events` builds an ordered
candidate list and `SoundPlayer::play_candidates` selects a sound. Candidate
lookup tries the selected pack, then the default pack, then the default
`alert` event. Single-event lookup has its own default-pack and `notify`
fallbacks. Missing or unreadable metadata can result in silence; do not
assume every malformed pack will fall back successfully.

## Validation and tests

`aw_audio::validate_sound_pack(&Path)` returns `(bool, String)`.
It checks the directory, metadata, referenced files, and per-event volumes.
It does not prove that every audio file can be decoded or that an output
device is available; use preview playback to check those.

Run from `rust/`:

```bash
cargo test -p aw-audio
```

Playback and UI checks still need an audio device and the target desktop.
See [TESTING.md](../TESTING.md) for workspace checks.
