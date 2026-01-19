"""Global settings storage for Kata."""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from kata.core.config import KATA_CONFIG_DIR

logger = logging.getLogger(__name__)

# Settings file location
SETTINGS_FILE = KATA_CONFIG_DIR / "settings.json"

# Legacy loop config file (for migration)
LEGACY_LOOP_CONFIG = KATA_CONFIG_DIR / "loop_config.json"

# Available themes (Kata custom themes)
AVAILABLE_THEMES = [
    "kata-dark",
    "kata-light",
    "kata-ocean",
    "kata-warm",
    "kata-glass",
    "kata-glass-light",
]


@dataclass
class Settings:
    """Global settings for Kata."""

    loop_enabled: bool = False
    default_group: str = "Uncategorized"
    refresh_interval: int = 5
    theme: str = "kata-dark"

    def __post_init__(self) -> None:
        """Validate and clamp values."""
        # Clamp refresh_interval to valid range (1-60)
        self.refresh_interval = max(1, min(60, self.refresh_interval))

        # Validate theme (allow legacy themes to fall back to kata-dark)
        if self.theme not in AVAILABLE_THEMES:
            self.theme = "kata-dark"

    def to_dict(self) -> dict[str, Any]:
        """Serialize settings to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        """Deserialize settings from dictionary."""
        return cls(
            loop_enabled=data.get("loop_enabled", False),
            default_group=data.get("default_group", "Uncategorized"),
            refresh_interval=data.get("refresh_interval", 5),
            theme=data.get("theme", "default"),
        )


def _migrate_from_legacy() -> Settings | None:
    """Migrate settings from legacy loop_config.json if it exists."""
    if not LEGACY_LOOP_CONFIG.exists():
        return None

    try:
        with open(LEGACY_LOOP_CONFIG) as f:
            data = json.load(f)

        loop_enabled = data.get("enabled", False)
        settings = Settings(loop_enabled=loop_enabled)
        logger.info(f"Migrated loop_enabled={loop_enabled} from legacy config")
        return settings
    except Exception as e:
        logger.warning(f"Failed to migrate legacy loop config: {e}")
        return None


def load_settings() -> Settings:
    """Load settings from JSON file with fallback to defaults.

    - If settings.json doesn't exist but loop_config.json does, migrate
    - If settings.json contains invalid JSON, use defaults and log warning
    - If settings.json doesn't exist, return defaults
    """
    if not SETTINGS_FILE.exists():
        # Try migration from legacy config
        migrated = _migrate_from_legacy()
        if migrated:
            # Save migrated settings
            save_settings(migrated)
            return migrated
        return Settings()

    try:
        with open(SETTINGS_FILE) as f:
            data = json.load(f)
        return Settings.from_dict(data)
    except json.JSONDecodeError as e:
        logger.warning(f"Settings file contains invalid JSON: {e}. Using defaults.")
        return Settings()
    except Exception as e:
        logger.warning(f"Failed to load settings: {e}. Using defaults.")
        return Settings()


def save_settings(settings: Settings) -> None:
    """Save settings to JSON file with atomic write.

    Uses write-to-temp-then-rename pattern for atomicity.
    """
    KATA_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = SETTINGS_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w") as f:
            json.dump(settings.to_dict(), f, indent=2)
            f.write("\n")  # Trailing newline

        # Atomic rename
        temp_file.rename(SETTINGS_FILE)
    except Exception as e:
        # Clean up temp file on failure
        if temp_file.exists():
            temp_file.unlink()
        raise RuntimeError(f"Failed to save settings: {e}") from e


# Singleton for app-wide access
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance (lazy-loaded singleton)."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def update_settings(**kwargs: Any) -> Settings:
    """Update specific settings and persist immediately.

    Example: update_settings(loop_enabled=True, refresh_interval=10)
    """
    settings = get_settings()

    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)

    # Re-validate after updates
    settings.__post_init__()

    save_settings(settings)
    return settings


def reload_settings() -> Settings:
    """Force reload settings from disk."""
    global _settings
    _settings = load_settings()
    return _settings
