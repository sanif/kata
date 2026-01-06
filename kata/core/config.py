"""Configuration paths and settings for Kata."""

from pathlib import Path

# Base configuration directory
KATA_CONFIG_DIR = Path.home() / ".config" / "kata"

# Registry file location
REGISTRY_FILE = KATA_CONFIG_DIR / "registry.json"

# Directory for tmuxp YAML configs
CONFIGS_DIR = KATA_CONFIG_DIR / "configs"


def ensure_config_dirs() -> None:
    """Create configuration directories if they don't exist."""
    KATA_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)


def get_config_path(project_name: str) -> Path:
    """Get the path to a project's tmuxp config file."""
    return CONFIGS_DIR / f"{project_name}.yaml"
