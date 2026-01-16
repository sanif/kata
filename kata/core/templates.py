"""tmuxp YAML template generation for projects."""

from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from kata.core.config import ensure_config_dirs, get_project_config_path
from kata.core.models import Project, ProjectType


class LayoutPreset(Enum):
    """Layout presets for tmux window/pane configurations."""

    MINIMAL = "minimal"  # Single editor window
    STANDARD = "standard"  # Editor + Shell + Tests (default)
    FULL = "full"  # Editor + Shell + Tests + Build + Logs
    CUSTOM = "custom"  # User will edit YAML manually after creation


# Base template structure for tmuxp
def _base_template(name: str, path: str) -> dict[str, Any]:
    """Create base template structure."""
    return {
        "session_name": name,
        "start_directory": path,
        "windows": [],
    }


def _python_template(name: str, path: str) -> dict[str, Any]:
    """Generate tmuxp template for Python projects."""
    template = _base_template(name, path)
    template["windows"] = [
        {
            "window_name": "editor",
            "panes": [{"shell_command": ["$EDITOR ."]}],
        },
        {
            "window_name": "shell",
            "panes": [
                {
                    "shell_command": [
                        "# Activate virtualenv if present",
                        "[ -f .venv/bin/activate ] && source .venv/bin/activate",
                    ]
                }
            ],
        },
        {
            "window_name": "tests",
            "panes": [
                {
                    "shell_command": [
                        "# Run tests with pytest",
                        "[ -f .venv/bin/activate ] && source .venv/bin/activate",
                    ]
                }
            ],
        },
    ]
    return template


def _node_template(name: str, path: str) -> dict[str, Any]:
    """Generate tmuxp template for Node.js projects."""
    template = _base_template(name, path)
    template["windows"] = [
        {
            "window_name": "editor",
            "panes": [{"shell_command": ["$EDITOR ."]}],
        },
        {
            "window_name": "dev",
            "panes": [
                {
                    "shell_command": [
                        "# Start dev server",
                        "# npm run dev",
                    ]
                }
            ],
        },
        {
            "window_name": "tests",
            "panes": [
                {
                    "shell_command": [
                        "# Run tests",
                        "# npm test",
                    ]
                }
            ],
        },
    ]
    return template


def _go_template(name: str, path: str) -> dict[str, Any]:
    """Generate tmuxp template for Go projects."""
    template = _base_template(name, path)
    template["windows"] = [
        {
            "window_name": "editor",
            "panes": [{"shell_command": ["$EDITOR ."]}],
        },
        {
            "window_name": "shell",
            "panes": [{"shell_command": []}],
        },
        {
            "window_name": "tests",
            "panes": [
                {
                    "shell_command": [
                        "# Run tests",
                        "# go test ./...",
                    ]
                }
            ],
        },
    ]
    return template


def _generic_template(name: str, path: str) -> dict[str, Any]:
    """Generate tmuxp template for generic projects."""
    template = _base_template(name, path)
    template["windows"] = [
        {
            "window_name": "main",
            "panes": [{"shell_command": ["$EDITOR ."]}],
        },
    ]
    return template


# Template generators by project type (legacy, used for STANDARD layout)
TEMPLATE_GENERATORS: dict[ProjectType, Any] = {
    ProjectType.PYTHON: _python_template,
    ProjectType.NODE: _node_template,
    ProjectType.GO: _go_template,
    ProjectType.GENERIC: _generic_template,
}


# Layout preset window generators
def _get_env_activation(project_type: ProjectType) -> list[str]:
    """Get environment activation commands for a project type."""
    if project_type == ProjectType.PYTHON:
        return [
            "# Activate virtualenv if present",
            "[ -f .venv/bin/activate ] && source .venv/bin/activate",
        ]
    return []


def _get_test_command(project_type: ProjectType) -> list[str]:
    """Get test runner command for a project type."""
    commands = {
        ProjectType.PYTHON: ["# Run tests with pytest", "# pytest"],
        ProjectType.NODE: ["# Run tests", "# npm test"],
        ProjectType.GO: ["# Run tests", "# go test ./..."],
        ProjectType.GENERIC: ["# Run tests"],
    }
    return commands.get(project_type, ["# Run tests"])


def _get_build_command(project_type: ProjectType) -> list[str]:
    """Get build/watch command for a project type."""
    commands = {
        ProjectType.PYTHON: ["# Build/watch", "# pip install -e ."],
        ProjectType.NODE: ["# Build/watch", "# npm run build"],
        ProjectType.GO: ["# Build", "# go build ./..."],
        ProjectType.GENERIC: ["# Build"],
    }
    return commands.get(project_type, ["# Build"])


def _minimal_windows(project_type: ProjectType) -> list[dict[str, Any]]:
    """Generate minimal layout: single editor window."""
    return [
        {
            "window_name": "editor",
            "panes": [{"shell_command": ["$EDITOR ."]}],
        },
    ]


def _standard_windows(project_type: ProjectType) -> list[dict[str, Any]]:
    """Generate standard layout: editor + shell + tests."""
    env_activation = _get_env_activation(project_type)
    test_commands = _get_test_command(project_type)

    shell_commands = env_activation if env_activation else []

    return [
        {
            "window_name": "editor",
            "panes": [{"shell_command": ["$EDITOR ."]}],
        },
        {
            "window_name": "shell",
            "panes": [{"shell_command": shell_commands}],
        },
        {
            "window_name": "tests",
            "panes": [
                {"shell_command": env_activation + test_commands if env_activation else test_commands}
            ],
        },
    ]


def _full_windows(project_type: ProjectType) -> list[dict[str, Any]]:
    """Generate full layout: editor (split) + shell + tests + build + logs."""
    env_activation = _get_env_activation(project_type)
    test_commands = _get_test_command(project_type)
    build_commands = _get_build_command(project_type)

    shell_commands = env_activation if env_activation else []

    return [
        {
            "window_name": "editor",
            "layout": "main-vertical",
            "panes": [
                {"shell_command": ["$EDITOR ."]},
                {"shell_command": ["git status"]},
            ],
        },
        {
            "window_name": "shell",
            "panes": [{"shell_command": shell_commands}],
        },
        {
            "window_name": "tests",
            "panes": [
                {"shell_command": env_activation + test_commands if env_activation else test_commands}
            ],
        },
        {
            "window_name": "build",
            "panes": [
                {"shell_command": env_activation + build_commands if env_activation else build_commands}
            ],
        },
        {
            "window_name": "logs",
            "layout": "even-vertical",
            "panes": [
                {"shell_command": ["# Application logs"]},
                {"shell_command": ["# System logs"]},
            ],
        },
    ]


# Layout preset to window generator mapping
LAYOUT_GENERATORS: dict[LayoutPreset, Any] = {
    LayoutPreset.MINIMAL: _minimal_windows,
    LayoutPreset.STANDARD: _standard_windows,
    LayoutPreset.FULL: _full_windows,
    LayoutPreset.CUSTOM: _minimal_windows,  # Custom starts with minimal, user edits after
}


def render_template(
    project: Project,
    project_type: ProjectType,
    layout_preset: LayoutPreset | None = None,
) -> dict[str, Any]:
    """Render a tmuxp template for a project.

    Args:
        project: The project to render template for
        project_type: Detected project type
        layout_preset: Layout preset to use (defaults to STANDARD)

    Returns:
        Template dictionary
    """
    if layout_preset is None:
        # Legacy behavior: use project-type-specific templates
        generator = TEMPLATE_GENERATORS.get(project_type, _generic_template)
        return generator(project.name, project.path)

    # New behavior: use layout preset with project-type-specific commands
    template = _base_template(project.name, project.path)
    window_generator = LAYOUT_GENERATORS.get(layout_preset, _standard_windows)
    template["windows"] = window_generator(project_type)
    return template


def write_template(
    project: Project,
    project_type: ProjectType,
    layout_preset: LayoutPreset | None = None,
) -> Path:
    """Write a tmuxp template to the project directory.

    Args:
        project: The project to write template for
        project_type: Detected project type
        layout_preset: Layout preset to use (defaults to STANDARD)

    Returns:
        Path to the written config file (.kata.yaml in project dir)
    """
    ensure_config_dirs()

    template = render_template(project, project_type, layout_preset)
    config_path = get_project_config_path(project.path)

    # Write YAML with proper formatting
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return config_path


def get_template_path(project: Project) -> Path:
    """Get the path to a project's tmuxp config file.

    Args:
        project: The project

    Returns:
        Path to the config file (.kata.yaml in project dir, may not exist)
    """
    return get_project_config_path(project.path)


def template_exists(project: Project) -> bool:
    """Check if a project's template file exists.

    Args:
        project: The project

    Returns:
        True if template exists
    """
    return get_template_path(project).exists()


def generate_adhoc_config(
    session_name: str,
    directory: str,
    project_type: ProjectType,
) -> dict[str, Any]:
    """Generate an in-memory tmuxp config for an adhoc session.

    Creates a temporary config for directories that aren't registered projects.
    Uses the standard layout based on the detected project type.

    Args:
        session_name: Name for the tmux session
        directory: Path to the directory
        project_type: Detected project type for the directory

    Returns:
        tmuxp-compatible config dictionary
    """
    template = _base_template(session_name, directory)
    template["windows"] = _standard_windows(project_type)
    return template
