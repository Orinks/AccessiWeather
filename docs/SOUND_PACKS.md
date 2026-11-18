# Using and Creating Sound Packs

Sound packs map weather and application events to audio files. Only the
`default` pack is bundled. Additional packs can be installed through the
Sound Pack Manager.

## Select and manage a pack

Open Settings and select the Audio tab. Choose a pack and use **Play sample
sound** to test it. Open the Sound Pack Manager to inspect mapped sounds,
preview them, import a ZIP, create a pack, duplicate or edit a pack, export
a ZIP, or browse community packs. The bundled default pack cannot be deleted
or shared as a custom pack.

Settings also has **Open sound packs folder** on its Advanced tab. Use that
button to find the directory for the current run instead of assuming a fixed
installation path.

## Pack format

Each pack has its own folder containing `pack.json` and its referenced files:

```text
my_pack/
  pack.json
  alert.ogg
  notify.ogg
```

```json
{
  "name": "My Pack",
  "author": "Your Name",
  "description": "Weather notification sounds",
  "version": "1.0.0",
  "sounds": {
    "alert": "alert.ogg",
    "notify": { "file": "notify.ogg", "volume": 0.5 }
  },
  "volumes": {
    "alert": 0.8
  }
}
```

The validator requires `name` and a `sounds` object, and checks that referenced
files exist. Author, description, and version describe the pack. Volume
values range from 0.0 to 1.0; a sound object uses its own volume, while a
plain filename uses the corresponding value in `volumes` or defaults to 1.0.

The playback dependency enables Ogg Vorbis, WAV, MP3, and FLAC decoding.
The bundled pack uses Ogg files. Keep cues short and balance their volume
against spoken output.

## Event mappings

Common events include `alert`, `notify`, `error`, `success`, `startup`,
`exit`, `data_updated`, `fetch_error`, and `discussion_update`.
Alert mappings also support severity and event-specific keys, such as
`warning`, `watch`, and `tornado_warning`. See the actual
[default pack](../soundpacks/default/pack.json) for its mappings.

The optional `specific_alert_sounds` boolean controls whether a pack prefers
event-specific alert cues. Without an explicit value, the app inspects the
pack's event mappings.

## Create or import

Use **Create Sound Pack...** in the manager for guided creation. For manual
creation, make a folder under the active sound packs directory, add
`pack.json` and the audio files, then reopen the manager. For ZIP import,
place `pack.json` and its referenced files at the archive root.

If a pack does not appear, check JSON syntax and the folder location.
If playback fails, check the referenced filenames, event mute settings,
the global sound setting, and the output device. Use the manager's preview
to distinguish a missing file from an event that is not being triggered.

See [Sound Pack System](SOUND_PACK_SYSTEM.md) for Rust integration details.
