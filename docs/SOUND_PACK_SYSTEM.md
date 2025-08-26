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

## Community Submission System

AccessiWeather features a **frictionless community submission system** that allows users to share their custom sound packs with the community without requiring any GitHub account setup or authentication barriers.

### Frictionless Submission Process

The community submission system is designed to be completely **barrier-free**:

- **No GitHub Account Required**: Users can submit packs without creating external accounts
- **No Authentication Setup**: No tokens, passwords, or OAuth flows required
- **One-Click Sharing**: Simple "Share with Community" button in the sound pack manager
- **Optional Attribution**: Users can provide their name/email for recognition or submit completely anonymously

### How Community Submission Works

#### User Experience

1. **Create Your Pack**: Build a custom sound pack using any of the creation methods above
2. **Open Sound Pack Manager**: Access the pack manager from the main settings
3. **Select Your Pack**: Choose the custom pack you want to share
4. **Click "Share with Community"**: No setup or authentication required
5. **Optional Attribution**: Dialog appears asking for optional name/email for community recognition
6. **Submit**: Pack is automatically submitted to the community repository

#### Behind the Scenes - GitHub App Authentication

The frictionless experience is powered by **GitHub App authentication** that handles all technical complexity:

- **AccessiBot Integration**: Uses AccessiBot (GitHub App) credentials for all GitHub operations
- **Secure Backend Auth**: JWT-based authentication with GitHub's App API
- **Professional Workflow**: Creates proper pull requests with full attribution and documentation
- **Automated Processing**: Handles fork creation, branch management, file uploads, and PR creation

### PackSubmissionService

The community submission is handled by the `PackSubmissionService` class, which provides two main methods:

#### Regular Submission (submit_pack)
```python
from accessiweather.services.pack_submission_service import PackSubmissionService

service = PackSubmissionService(
    repo_owner="accessiweather-community",
    repo_name="soundpacks", 
    dest_subdir="packs",
    config_manager=config_manager
)

# Submit pack with GitHub App authentication
pr_url = await service.submit_pack(pack_path, pack_metadata)
```

#### Anonymous Submission (submit_pack_anonymous)
```python
# Submit pack anonymously with optional attribution
pr_url = await service.submit_pack_anonymous(
    pack_path, 
    pack_metadata,
    submitter_name="John Doe",  # Optional
    submitter_email="john@example.com",  # Optional
    progress_callback=progress_callback
)
```

### GitHubAppClient Integration

The submission service uses `GitHubAppClient` for secure authentication:

```python
from accessiweather.services.github_app_client import GitHubAppClient

# Create GitHub App client
client = GitHubAppClient(
    app_id=app_id,
    private_key_pem=private_key,
    installation_id=installation_id,
    user_agent="AccessiWeather/0.9.4-dev"
)

# Perform authenticated API requests
repo_info = await client.github_request("GET", "/repos/accessiweather-community/soundpacks")
```

#### Authentication Flow

1. **JWT Generation**: Creates signed JWT token using GitHub App private key
2. **Installation Token**: Exchanges JWT for installation access token via `/app/installations/{id}/access_tokens`
3. **Resource Access**: Uses installation token for all repository operations
4. **Proper Auth Schemes**: 
   - `Authorization: Bearer <jwt>` for GitHub App endpoints
   - `Authorization: token <token>` for resource endpoints

### Security and Privacy

The community submission system maintains strong security practices:

#### Privacy Protection
- **Optional Attribution**: Users choose whether to provide identifying information
- **Clear Privacy Messaging**: Users understand exactly how attribution information is used
- **Anonymous Submission Support**: Complete anonymity option available

#### Security Features
- **No User Credentials**: No storage or transmission of user GitHub credentials
- **Backend Authentication**: All GitHub operations use secure App authentication
- **Validation**: Comprehensive pack validation before submission
- **Duplicate Detection**: Prevents submission of existing packs

### Error Handling and User Experience

#### Quality-Focused Validation
- **Pack Completeness**: Ensures all required sounds and metadata are present
- **Content Quality**: Validates audio files and pack structure
- **User-Friendly Messages**: Clear guidance on improving pack quality rather than technical errors

#### Graceful Failure Handling
- **Connection Issues**: Clear messaging when GitHub is unavailable
- **Validation Failures**: Specific guidance on fixing pack issues
- **Cancellation Support**: Users can cancel submission at any point

### Testing

The community submission system includes comprehensive testing:

#### Test Coverage Areas
- **GitHub App Authentication**: Mock JWT generation and token exchange
- **Anonymous Submission Flow**: Full workflow testing with attribution metadata
- **Error Scenarios**: Validation failures, network issues, cancellation
- **Fork Management**: Installation-based fork creation and management
- **Duplicate Detection**: Preflight checks for existing packs

#### Running Submission Tests
```bash
# Test community submission functionality
pytest tests/test_sound_pack_system_submission.py

# Test with verbose output
pytest tests/test_sound_pack_system_submission.py -v

# Test specific scenarios
pytest tests/test_sound_pack_system_submission.py::test_submit_pack_anonymous_comprehensive
```

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

The sound pack system includes comprehensive tests covering all functionality:

### Core System Tests
- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing  
- **Dialog Tests**: UI component testing with Toga dummy backend
- **Error Handling Tests**: Validation and fallback testing

### Community Submission Tests
- **GitHub App Authentication**: JWT generation and installation token exchange
- **Anonymous Submission Flow**: Full workflow with attribution metadata
- **Error Scenarios**: Validation failures, network issues, and cancellation
- **Fork Management**: Installation-based repository operations
- **Duplicate Detection**: Preflight checks for existing community packs

### Running Tests

```bash
# Core sound pack system tests
pytest tests/test_sound_pack_system.py
pytest tests/test_sound_pack_installer.py
pytest tests/test_sound_pack_integration.py

# Community submission tests
pytest tests/test_sound_pack_system_submission.py

# Run all sound pack tests
pytest tests/test_sound_pack*.py

# Verbose output for debugging
pytest tests/test_sound_pack_system_submission.py -v
```

## File Locations

### Core Sound Pack System
- **Sound Packs**: `src/accessiweather/soundpacks/`
- **Core Module**: `src/accessiweather/notifications/sound_player.py`
- **Manager Dialog**: `src/accessiweather/dialogs/soundpack_manager_dialog.py`
- **Installer**: `src/accessiweather/notifications/sound_pack_installer.py`

### Community Submission System
- **Submission Service**: `src/accessiweather/services/pack_submission_service.py`
- **GitHub App Client**: `src/accessiweather/services/github_app_client.py`

### Tests
- **Core Tests**: `tests/test_sound_pack_*.py`
- **Submission Tests**: `tests/test_sound_pack_system_submission.py`

## Dependencies

### Core System Dependencies
- **playsound**: Audio playback functionality
- **toga**: GUI framework for dialogs
- **pathlib**: File system operations
- **json**: Pack metadata handling
- **zipfile**: Pack import/export functionality

### Community Submission Dependencies
- **httpx**: HTTP client for GitHub API requests
- **cryptography**: JWT signing for GitHub App authentication
- **asyncio**: Asynchronous operation support

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
