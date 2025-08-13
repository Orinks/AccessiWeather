# AccessiWeather Sound Pack System

The AccessiWeather sound pack system provides customizable audio notifications for weather events and application interactions. This system is designed with accessibility in mind, offering users the ability to choose from different sound themes or create their own custom sound packs.

## Overview

The sound pack system consists of several key components:

1. **Sound Player** (`sound_player.py`) - Core functionality for playing sounds
2. **Sound Pack Manager Dialog** (`soundpack_manager_dialog.py`) - GUI for managing sound packs
3. **Sound Pack Installer** (`sound_pack_installer.py`) - Installation and management utilities
4. **Built-in Sound Packs** - Default, Nature, and Minimal themes

## Sound Pack Structure

Each sound pack is a directory containing:

- `pack.json` - Metadata and sound file mappings
- Audio files (`.wav` format recommended)

### pack.json Format

```json
{
    "name": "Display Name",
    "author": "Author Name",
    "description": "Pack description",
    "version": "1.0.0",
    "sounds": {
        "alert": "alert_sound.wav",
        "notify": "notification_sound.wav",
        "error": "error_sound.wav",
        "success": "success_sound.wav"
    }
}
```

### Required Sound Events

- `alert` - Weather alerts and important notifications
- `notify` - General notifications
- `error` - Error conditions
- `success` - Successful operations

## Built-in Sound Packs

### Default Pack
- Standard system sounds
- Balanced volume and tone
- Suitable for most users

### Nature Pack
- Bird chirps for alerts
- Water drops for notifications
- Distant thunder for errors
- Gentle rain for success

### Minimal Pack
- Subtle beeps and chimes
- Low volume, unobtrusive
- Ideal for quiet environments

## Usage

### Playing Sounds

```python
from accessiweather.notifications.sound_player import play_notification_sound

# Play an alert sound using the default pack
play_notification_sound("alert", "default")

# Play a notification sound using the nature pack
play_notification_sound("notify", "nature")
```

### Managing Sound Packs

```python
from accessiweather.notifications.sound_pack_installer import SoundPackInstaller
from pathlib import Path

installer = SoundPackInstaller(Path("soundpacks"))

# Install from ZIP file
success, message = installer.install_from_zip(Path("my_pack.zip"), "my_pack")

# Create a new pack template
pack_info = {
    "name": "My Custom Pack",
    "author": "Your Name",
    "description": "Custom sound pack"
}
success, message = installer.create_pack_template("custom", pack_info)

# List installed packs
packs = installer.list_installed_packs()

# Export a pack
success, message = installer.export_pack("my_pack", Path("exported.zip"))

# Uninstall a pack
success, message = installer.uninstall_pack("my_pack")
```

### Getting Available Packs

```python
from accessiweather.notifications.sound_player import get_available_sound_packs

packs = get_available_sound_packs()
for pack_id, pack_info in packs.items():
    print(f"{pack_info['name']} by {pack_info['author']}")
```

## Integration with Settings

The sound pack system is integrated into the main application settings:

1. **Sound Pack Selection** - Dropdown to choose active sound pack
2. **Preview Button** - Test sounds from selected pack
3. **Manage Sound Packs** - Opens the sound pack manager dialog

## Sound Pack Manager Dialog

The sound pack manager provides a GUI for:

- Viewing installed sound packs
- Previewing sounds from different packs
- Selecting the active sound pack
- Installing new packs from ZIP files
- Deleting unwanted packs
- Viewing pack information and sound lists

## Creating Custom Sound Packs

### Method 1: Using the Template System

1. Use `SoundPackInstaller.create_pack_template()` to create a basic structure
2. Replace the placeholder `.wav` files with your custom sounds
3. Update the `pack.json` metadata as needed

### Method 2: Manual Creation

1. Create a new directory in the soundpacks folder
2. Add a `pack.json` file with required metadata
3. Add audio files referenced in the sounds mapping
4. Ensure all sound files exist and are playable

### Method 3: ZIP Installation

1. Create a ZIP file containing `pack.json` and audio files
2. Use the sound pack manager or installer to import the ZIP
3. The system will validate and install the pack automatically

## Audio File Requirements

- **Format**: WAV files recommended for best compatibility
- **Duration**: Keep sounds short (1-3 seconds) for notifications
- **Volume**: Normalize volume levels across all sounds in a pack
- **Quality**: 16-bit, 44.1kHz recommended for good quality/size balance

## Error Handling and Fallbacks

The sound pack system includes robust error handling:

1. **Missing Sound Files**: Falls back to default pack
2. **Invalid pack.json**: Logs error and uses default pack
3. **Corrupted Audio**: Gracefully handles playback failures
4. **Missing Packs**: Always provides default pack as fallback

## Accessibility Features

- **Screen Reader Support**: All UI elements properly labeled
- **Keyboard Navigation**: Full keyboard access to all functions
- **Sound Previews**: Test sounds before applying changes
- **Clear Feedback**: Status messages for all operations
- **Fallback Behavior**: Ensures sounds always work

## Testing

The sound pack system includes comprehensive tests:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **Dialog Tests**: UI component testing with Toga dummy backend
- **Error Handling Tests**: Validation and fallback testing

Run tests with:
```bash
pytest tests/test_sound_pack_system.py
pytest tests/test_sound_pack_installer.py
pytest tests/test_sound_pack_integration.py
```

## File Locations

- **Sound Packs**: `src/accessiweather/soundpacks/`
- **Core Module**: `src/accessiweather/notifications/sound_player.py`
- **Manager Dialog**: `src/accessiweather/dialogs/soundpack_manager_dialog.py`
- **Installer**: `src/accessiweather/notifications/sound_pack_installer.py`
- **Tests**: `tests/test_sound_pack_*.py`

## Dependencies

- **playsound**: Audio playback functionality
- **toga**: GUI framework for dialogs
- **pathlib**: File system operations
- **json**: Pack metadata handling
- **zipfile**: Pack import/export functionality

## Future Enhancements

Potential improvements for the sound pack system:

1. **Online Pack Repository**: Download packs from a central repository
2. **Volume Controls**: Per-pack volume adjustment
3. **Sound Mixing**: Layer multiple sounds for complex notifications
4. **Format Support**: Support for MP3, OGG, and other audio formats
5. **Pack Validation**: More comprehensive validation rules
6. **Pack Signing**: Digital signatures for trusted packs
7. **Accessibility Enhancements**: Audio descriptions for sound packs
8. **Localization**: Multi-language pack descriptions

## Troubleshooting

### Common Issues

**Sounds not playing:**
- Check if playsound is installed: `pip install playsound`
- Verify audio files exist and are not corrupted
- Check system audio settings and volume

**Pack installation fails:**
- Ensure ZIP file contains valid pack.json
- Check that all referenced sound files exist in the ZIP
- Verify pack.json has required fields (name, sounds)

**Dialog not opening:**
- Check for Toga installation issues
- Verify all UI components are properly initialized
- Look for error messages in application logs

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.getLogger('accessiweather.notifications').setLevel(logging.DEBUG)
```

This will provide detailed information about sound pack loading, file operations, and error conditions.
