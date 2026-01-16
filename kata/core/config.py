"""Configuration paths and settings for Kata."""

import shutil
from pathlib import Path

# Base configuration directory
KATA_CONFIG_DIR = Path.home() / ".config" / "kata"

# Registry file location
REGISTRY_FILE = KATA_CONFIG_DIR / "registry.json"

# Config filename stored in each project
KATA_CONFIG_FILENAME = ".kata.yaml"

# Legacy configs directory (for migration)
LEGACY_CONFIGS_DIR = KATA_CONFIG_DIR / "configs"


def ensure_config_dirs() -> None:
    """Create configuration directories if they don't exist."""
    KATA_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def get_project_config_path(project_path: str | Path) -> Path:
    """Get the path to a project's tmuxp config file.

    Config is stored as .kata.yaml inside the project directory.
    """
    return Path(project_path) / KATA_CONFIG_FILENAME


def migrate_project_config(project_name: str, project_path: str | Path) -> bool:
    """Migrate a project's config from legacy location to project folder.

    Moves config from ~/.config/kata/configs/{name}.yaml to {project}/.kata.yaml

    Args:
        project_name: Name of the project (used for legacy filename)
        project_path: Path to the project directory

    Returns:
        True if migration occurred, False if no migration needed
    """
    legacy_path = LEGACY_CONFIGS_DIR / f"{project_name}.yaml"
    new_path = get_project_config_path(project_path)

    # Skip if legacy doesn't exist or new already exists
    if not legacy_path.exists() or new_path.exists():
        return False

    # Move the config file
    try:
        shutil.move(str(legacy_path), str(new_path))
        return True
    except Exception:
        # If move fails, try copy
        try:
            shutil.copy2(str(legacy_path), str(new_path))
            legacy_path.unlink()  # Remove old file after successful copy
            return True
        except Exception:
            return False


def migrate_all_configs() -> dict[str, bool]:
    """Migrate all configs from legacy location to project folders.

    Reads the registry and migrates each project's config.

    Returns:
        Dict mapping project name to migration success
    """
    import json

    results: dict[str, bool] = {}

    if not REGISTRY_FILE.exists():
        return results

    try:
        with open(REGISTRY_FILE) as f:
            data = json.load(f)

        for project_data in data.get("projects", []):
            name = project_data.get("name")
            path = project_data.get("path")
            if name and path:
                results[name] = migrate_project_config(name, path)
    except Exception:
        pass

    return results
