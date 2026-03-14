# Coding Conventions

**Analysis Date:** 2026-03-14

## Naming Patterns

**Files:**
- Snake_case: `weather_client.py`, `alert_manager.py`, `openmeteo_client.py`
- Test files: `test_cache.py`, `test_alert_manager.py`
- Dunder files allowed: `__init__.py`, `__main__.py`

**Functions:**
- Snake_case: `geocode_address()`, `fetch_weather()`, `validate_coordinates()`
- Private functions: Leading underscore `_safe_location_key()`, `_serialize_datetime()`
- Test functions: Always start with `test_`: `test_set_and_get()`, `test_expired_entry_returns_none()`

**Variables:**
- Snake_case: `location`, `weather_data`, `default_ttl`, `content_hash`
- Constants: UPPER_CASE: `ALLOWED_COUNTRY_CODES`, `CACHE_SCHEMA_VERSION`, `DEFAULT_TIMEOUT`
- Private instance variables: Leading underscore `self._path_for_location()`

**Classes:**
- PascalCase: `Cache`, `WeatherDataCache`, `AlertManager`, `AlertState`, `GeocodingService`
- Always import from `abc` module: `from abc import ABC, abstractmethod`

**Type Hints:**
- Modern syntax: `dict[str, Any]` not `Dict[str, Any]`
- Optional notation: `value: str | None` not `Optional[str]`
- List notation: `list[str]` not `List[str]`
- Use `from __future__ import annotations` at file top

## Code Style

**Formatting:**
- Tool: Ruff (enforced via pre-commit)
- Line length: 100 characters (configured in `pyproject.toml` at `[tool.ruff]`)
- Quote style: Double quotes only (`"string"` not `'string'`)
- Indent: 4 spaces (no tabs)

**Linting:**
- Tool: Ruff (rules in `[tool.ruff.lint]`)
- Enabled rules: `E`, `W`, `F`, `I`, `D`, `UP`, `B`, `C4`, `PIE`, `SIM`, `RET`
- Notable disabled: Docstring rules (`D100-D105`), complexity checks (`C901`)
- Per-file exceptions in `[tool.ruff.lint.per-file-ignores]`

**Type Checking:**
- Tool: Pyright (available but not integrated into CI)
- Not enforced in pre-commit hooks
- Optional for manual verification

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first if present)
2. Stdlib: `import asyncio`, `import logging`, `from typing import TYPE_CHECKING`
3. Third-party: `import httpx`, `import pytest`, `from hypothesis import settings`
4. Local: `from .config import ConfigManager`, `from .models import Location`
5. Type-only imports in `if TYPE_CHECKING:` block (bottom)

**Path Aliases:**
- Relative imports used for local package imports: `from .cache import Cache`
- Absolute imports from installed packages: `from accessiweather.models import Location`
- No import aliases except for clarity: `from . import weather_client_nws as nws_client`

**Example Structure:**
```python
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from .cache import Cache
from .models import WeatherData, Location

if TYPE_CHECKING:
    from .alert_manager import AlertManager

logger = logging.getLogger(__name__)
```

## Error Handling

**Patterns:**
- Catch specific exceptions, not bare `except:` (though `except Exception as e:` with `# noqa: BLE001` is used for broad catches)
- Use `getattr(obj, 'attr', default)` for defensive attribute access
- Wrap external API calls in try-except blocks
- Log exceptions at appropriate level: `logger.debug()`, `logger.warning()`, `logger.error()`
- Return `None` or default values on error, don't let exceptions propagate in API clients

**Example from `cache.py`:**
```python
def load(self, location: Location, *, allow_stale: bool = True) -> WeatherData | None:
    try:
        with path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Failed to read cached weather data: {exc}")
        return None
```

**Validation Pattern:**
- Check types before processing: `if isinstance(data, dict):`
- Validate numeric ranges: `-90 <= lat <= 90`, `0 <= humidity <= 100`
- Defensive type narrowing prevents runtime errors

## Logging

**Framework:** Built-in `logging` module

**Pattern:**
```python
logger = logging.getLogger(__name__)
```

**When to Log:**
- DEBUG: Detailed diagnostic info (cache hits/misses, API call details, data conversions)
- INFO: General informational messages (cache initialization, config loaded)
- WARNING: Something unexpected but recoverable (API timeout, stale data)
- ERROR: Something failed (API error, file I/O failure)

**Examples from codebase:**
```python
logger.debug(f"Cache hit for '{key}' (expires in {int(entry.expiration - current_time)}s)")
logger.warning("Request timed out")
logger.info(f"Initialized {self.__class__.__name__} with User-Agent: {self.user_agent}")
```

**Sensitive Data:**
- NEVER log API keys, tokens, or credentials
- Mask secrets: `logger.info(f"Using key: {api_key[:4]}...")` if needed
- Use `logger.debug()` for development, not `print()`

## Comments

**When to Comment:**
- Explain WHY, not WHAT (code shows what it does)
- Non-obvious logic or algorithms
- Important design decisions
- Workarounds for known issues/limitations

**Docstrings:**
- Use triple-quoted docstrings for modules, classes, public functions
- Format: Description, empty line, Args/Returns/Raises (Google-style)
- Example from `cache.py`:
```python
def get(self, key: str) -> Any | None:
    """
    Get a value from the cache.

    Args:
    ----
        key: The cache key

    Returns:
    -------
        The cached value or None if not found or expired

    """
```

**JSDoc-style not used** - Python uses docstrings, not JSDoc

## Function Design

**Size:**
- Prefer small functions (< 20 lines)
- Break complex operations into helpers
- Private helper functions use leading underscore

**Parameters:**
- Positional args for required parameters
- Keyword-only args after `*` for optional config: `def load(self, location: Location, *, allow_stale: bool = True)`
- Type hints always included

**Return Values:**
- Single return type: `-> str | None`
- Use dataclasses for multiple returns: `Location(name=..., latitude=..., longitude=...)`
- Explicit None returns for optional values

**Example from `geocoding.py`:**
```python
def geocode_address(self, address: str) -> tuple[float, float, str] | None:
    """Convert address to coordinates."""
    # Returns (lat, lon, country_code) tuple or None
```

## Module Design

**Exports:**
- Use `__all__` to document public API: `__all__ = ["WeatherClient"]`
- Keep modules focused on single responsibility

**Barrel Files:**
- `__init__.py` files re-export public classes for convenience:
```python
# src/accessiweather/models/__init__.py
from .weather import Location, WeatherData
from .alerts import WeatherAlert

__all__ = ["Location", "WeatherData", "WeatherAlert"]
```

**File Organization:**
- One main class per file (except models package)
- Helper/private functions in same file
- Related functionality grouped in packages: `api/`, `services/`, `config/`

## Dataclass Patterns

**Used throughout for data models:**
- `Location`, `CurrentConditions`, `Forecast`, `WeatherAlert`, etc.
- Located in `src/accessiweather/models/` subdirectory
- Support serialization/deserialization for cache storage
- Immutable-style: minimal methods, mostly field access

**Example from `models/weather.py`:**
```python
@dataclass
class Location:
    name: str
    latitude: float
    longitude: float
    country_code: str | None = None
```

## Testing Patterns (In Code)

**Use pytest class grouping:**
- `TestClassName` groups related tests
- Improves readability and fixture sharing
- One assertion per test (general rule, sometimes 2-3 for data validation)

**Fixture pattern:**
```python
@pytest.fixture
def cache(self, tmp_path):
    return WeatherDataCache(tmp_path, max_age_minutes=60)
```

---

*Convention analysis: 2026-03-14*
