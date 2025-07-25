# AccessiWeather Sound Pack System

The AccessiWeather sound pack system allows users to customize notification sounds by creating and importing custom sound packs. This document explains how to use, create, and manage sound packs.

## Overview

Sound packs are collections of audio files organized in a specific directory structure with metadata. Each sound pack contains:

- **pack.json**: Metadata file describing the sound pack
- **Sound files**: WAV audio files for different notification types
- **Directory structure**: Organized in the `soundpacks/` directory

## Directory Structure

```
src/accessiweather/soundpacks/
├── default/
│   ├── pack.json
│   ├── alert.wav
│   └── notify.wav
├── classic/
│   ├── pack.json
│   ├── alert.wav
│   └── notify.wav
└── [other_packs]/
    ├── pack.json
    └── [sound_files]
```

## Sound Pack Format

### pack.json Structure

Each sound pack must include a `pack.json` file with the following structure:

```json
{
    "name": "Display Name",
    "author": "Author Name",
    "description": "Description of the sound pack",
    "version": "1.0.0",
    "sounds": {
        "alert": "alert_sound_file.wav",
        "notify": "notification_sound_file.wav"
    }
}
```

### Required Fields

- **name**: Human-readable name for the sound pack
- **sounds**: Object mapping sound types to file names

### Optional Fields

- **author**: Creator of the sound pack
- **description**: Brief description of the sound pack
- **version**: Version number of the sound pack

### Sound Types

Currently supported sound types:

- **alert**: Weather alert notifications
- **notify**: General notifications

## Using Sound Packs

### Selecting a Sound Pack

1. Open AccessiWeather settings
2. Go to the "General" tab
3. Find the "Sound Pack" dropdown
4. Select your preferred sound pack
5. Click "Preview Sound" to test the selected pack
6. Save settings

### Managing Sound Packs

1. Open AccessiWeather settings
2. Go to the "General" tab
3. Click "Manage Sound Packs..." button
4. The Sound Pack Manager dialog will open

#### Sound Pack Manager Features

- **View available packs**: See all installed sound packs
- **Pack details**: View information about each pack
- **Sound list**: See all sounds in a pack with their status
- **Preview sounds**: Test individual sounds from any pack
- **Import packs**: Add new sound packs from ZIP files
- **Delete packs**: Remove unwanted sound packs (except default)
- **Select pack**: Choose the active sound pack

## Creating Custom Sound Packs

### Method 1: Manual Creation

1. Create a new directory in `src/accessiweather/soundpacks/`
2. Name the directory with a unique identifier (e.g., `my_custom_pack`)
3. Create a `pack.json` file with the required metadata
4. Add your WAV audio files to the directory
5. Restart AccessiWeather to detect the new pack

### Method 2: ZIP Import

1. Create a ZIP file containing:
   - `pack.json` file
   - All referenced sound files
2. Use the Sound Pack Manager to import the ZIP file
3. The pack will be automatically extracted and validated

### Audio File Requirements

- **Format**: WAV files recommended (MP3 may work but not guaranteed)
- **Sample Rate**: 44.1kHz recommended
- **Bit Depth**: 16-bit recommended
- **Duration**: 1-3 seconds for best user experience
- **Volume**: Normalized to prevent overly loud or quiet sounds

### Example Sound Pack Creation

```bash
# Create directory structure
mkdir my_nature_pack
cd my_nature_pack

# Create pack.json
cat > pack.json << EOF
{
    "name": "Nature Sounds",
    "author": "Your Name",
    "description": "Peaceful nature sounds for notifications",
    "version": "1.0.0",
    "sounds": {
        "alert": "bird_chirp.wav",
        "notify": "water_drop.wav"
    }
}
EOF

# Add your sound files
# bird_chirp.wav
# water_drop.wav

# Create ZIP for distribution
zip -r nature_sounds_pack.zip *
```

## Built-in Sound Packs

### Default Pack
- **Name**: Default
- **Description**: Standard notification sounds
- **Sounds**: Generated modern notification sounds

### Classic Pack
- **Name**: Classic
- **Description**: Retro computer-style sounds
- **Sounds**: Classic beep-style notifications

## Troubleshooting

### Sound Pack Not Appearing

1. Check that `pack.json` exists and is valid JSON
2. Verify all referenced sound files exist
3. Ensure the pack directory is in the correct location
4. Restart AccessiWeather

### Sounds Not Playing

1. Check that sound files are in WAV format
2. Verify file paths in `pack.json` are correct
3. Test with the "Preview Sound" button
4. Check system audio settings

### Import Errors

1. Ensure ZIP file contains `pack.json` at the root level
2. Verify all referenced sound files are included
3. Check that pack name doesn't conflict with existing packs
4. Validate JSON syntax in `pack.json`

## API Reference

### Sound Player Functions

```python
from accessiweather.notifications.sound_player import (
    get_available_sound_packs,
    get_sound_pack_sounds,
    validate_sound_pack,
    play_notification_sound,
    play_sample_sound
)

# Get all available sound packs
packs = get_available_sound_packs()

# Get sounds in a specific pack
sounds = get_sound_pack_sounds("default")

# Validate a sound pack
is_valid, message = validate_sound_pack(pack_path)

# Play a notification sound
play_notification_sound("alert", "default")

# Play a sample sound
play_sample_sound("default")
```

## Contributing Sound Packs

If you create high-quality sound packs that you'd like to share:

1. Ensure all sounds are original or properly licensed
2. Test thoroughly with the validation system
3. Include clear attribution in the pack metadata
4. Consider creating both ZIP and directory versions
5. Document any special requirements or themes

## Technical Details

### Sound Pack Loading

Sound packs are loaded dynamically at runtime by scanning the `soundpacks/` directory for subdirectories containing valid `pack.json` files.

### Fallback Behavior

If a requested sound pack or sound file is not found, the system falls back to:
1. The default pack for the same sound type
2. A silent operation if the default pack is unavailable

### Performance Considerations

- Sound files are loaded on-demand, not cached in memory
- Pack metadata is cached for performance
- Large sound files may cause brief delays during playback

## Future Enhancements

Planned features for future versions:

- Support for additional sound formats (MP3, OGG)
- More sound types (startup, shutdown, error, etc.)
- Sound pack themes and categories
- Online sound pack repository
- Visual sound waveform preview
- Volume control per sound pack
- Sound pack export functionality
