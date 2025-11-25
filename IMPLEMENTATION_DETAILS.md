# Implementation Details: Update Settings Synchronization Fix

## The Problem

The application had **two separate settings systems** that were never synchronized:

1. **AppSettings** (in `models/config.py`)
   - Used by the main application
   - Stored in `~/.config/accessiweather/config.json`
   - Has field: `update_channel: str`

2. **UpdateSettings** (in `services/update_service/settings.py`)
   - Used by the GitHub update service
   - Stored in `~/.config/accessiweather/update_settings.json`
   - Has field: `channel: str`

When a user changed the update channel via Settings → Updates → "Update Channel", only `AppSettings.update_channel` was updated. The `UpdateSettings.channel` remained unchanged, so the updater continued using the old channel value.

### Example Scenario

1. App starts → UpdateSettings.channel defaults to "stable"
2. User sets channel to "Development" in Settings
3. AppSettings.update_channel = "dev" (saved)
4. User clicks "Check for Updates"
5. UpdateSettings.channel is still "stable" ❌
6. Updater fetches releases filtered for "stable" channel
7. Nightly releases are excluded (because they're not "stable")
8. User sees: "No updates available" ❌

## The Solution

### Step 1: Create Sync Function

**File: `src/accessiweather/services/update_service/sync_settings.py`**

```python
def sync_update_channel_to_service(
    config_manager: ConfigManager | None,
    update_service: GitHubUpdateService | None,
) -> None:
    """Sync AppSettings.update_channel to UpdateSettings.channel"""
    if not config_manager or not update_service:
        return

    try:
        config = config_manager.get_config()
        if config and config.settings:
            app_channel = getattr(config.settings, "update_channel", "stable")
            old_channel = update_service.settings.channel

            # Update the channel
            update_service.settings.channel = app_channel

            # If channel changed, invalidate cache to fetch fresh releases
            if old_channel != app_channel:
                logger.info(f"Channel changed from '{old_channel}' to '{app_channel}', clearing cache")
                update_service.release_manager._cache = None
    except Exception as exc:
        logger.warning(f"Failed to sync update channel: {exc}")
```

**Key Points:**
- Copies `AppSettings.update_channel` → `UpdateSettings.channel`
- Only syncs if both managers exist (defensive programming)
- Invalidates cache when channel changes (forces fresh fetch)
- Logs channel changes for debugging

### Step 2: Call Sync at Initialization

**File: `src/accessiweather/app_initialization.py`**

```python
try:
    from .services import GitHubUpdateService, sync_update_channel_to_service

    app.update_service = GitHubUpdateService(...)

    # NEW: Sync the update channel from AppSettings to UpdateSettings
    sync_update_channel_to_service(app.config_manager, app.update_service)
    logger.info("Update service initialized")
except Exception as exc:
    logger.warning("Failed to initialize update service: %s", exc)
    app.update_service = None
```

**When:** On app startup, right after creating the update service.

**Why:** Ensures both settings are in sync from the beginning.

### Step 3: Call Sync Before Manual Update Check

**File: `src/accessiweather/handlers/update_handlers.py`**

```python
async def on_check_updates_pressed(app: AccessiWeatherApp, widget: toga.Command) -> None:
    """Handle check for updates menu item."""
    if not app.update_service:
        return

    try:
        from ..services import sync_update_channel_to_service

        # NEW: Sync the update channel before checking for updates
        sync_update_channel_to_service(app.config_manager, app.update_service)

        app_helpers.update_status(app, "Checking for updates...")
        update_info = await app.update_service.check_for_updates()
        # ... rest of function
```

**When:** User clicks "Check for Updates" from the menu.

**Why:** Guarantees the latest AppSettings are used before any update check.

### Step 4: Save and Sync in Settings Dialog

**File: `src/accessiweather/dialogs/settings_operations.py`**

```python
async def check_for_updates(dialog):
    """Trigger an update check with channel syncing"""
    # ... setup code ...

    channel_value = str(dialog.update_channel_selection.value)
    channel = settings_handlers.map_channel_display_to_value(channel_value)

    # NEW: Save to AppSettings
    if dialog.config_manager:
        dialog.config_manager.settings.update_settings(update_channel=channel)

    # NEW: Sync to UpdateSettings
    from ..services import sync_update_channel_to_service
    sync_update_channel_to_service(dialog.config_manager, update_service)

    # Now check for updates with synced settings
    update_info = await asyncio.wait_for(
        update_service.check_for_updates(), timeout=timeout_seconds
    )
```

**When:** User changes channel and clicks "Check for Updates" in Settings dialog.

**Why:**
- Saves user's selection to AppSettings (persistence)
- Syncs to UpdateSettings immediately (ensures it's used)
- Fetches fresh releases with the new channel

## How Cache Invalidation Works

The `ReleaseManager` validates cache like this (in `releases.py`):

```python
cache_valid = (
    self._cache
    and self._cache.get("last_check", 0) + CACHE_EXPIRY_SECONDS > time.time()
    and self._cache.get("channel") == self.settings.channel  # <-- THIS CHECK
    and self._cache.get("owner") == self.owner
    and self._cache.get("repo") == self.repo
)
```

**Dual Protection:**

1. **In-memory cache cleared immediately:**
   ```python
   update_service.release_manager._cache = None
   ```
   - Next fetch creates new in-memory cache

2. **Disk cache automatically invalidated:**
   - Disk cache still has old channel value
   - When loaded, the channel check fails
   - Cached releases are rejected
   - Fresh releases fetched from GitHub

## Testing

**File: `tests/test_update_settings_sync.py`** includes:

```python
def test_sync_updates_channel_different(mock_config_manager, mock_update_service):
    """Test sync when channel needs to be updated"""
    mock_config_manager.get_config().settings.update_channel = "dev"
    mock_update_service.settings.channel = "stable"

    sync_update_channel_to_service(mock_config_manager, mock_update_service)

    # Verify channel was updated
    assert mock_update_service.settings.channel == "dev"
    # Verify cache was cleared
    assert mock_update_service.release_manager._cache is None
```

**All 10 tests pass:**
- None managers handled gracefully
- Channel syncing works correctly
- Cache invalidation works
- Missing settings handled safely
- All channel values supported (stable, dev, beta, nightly)

## Result

Now when a user:

1. **Changes the update channel to "Development":**
   - Setting saved to AppSettings ✓
   - Synced to UpdateSettings ✓
   - Cache cleared ✓
   - Fresh releases fetched ✓

2. **Clicks "Check for Updates":**
   - Settings synced before check ✓
   - Latest nightly releases visible ✓

3. **Restarts the app:**
   - AppSettings loaded from disk ✓
   - UpdateSettings synced on init ✓
   - Channel setting preserved ✓

## No Breaking Changes

- Existing code paths unaffected
- New function is additive only
- All existing tests continue to pass
- Settings migration still works ("nightly" → "dev")
