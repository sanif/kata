"""Pilot tests for the KataDashboard empty-state -> populated transition."""

import json
from unittest.mock import patch

import pytest

import kata.services.registry as registry_module
from kata.core.models import Project


@pytest.fixture
def isolated_registry(tmp_path):
    """Point the registry singleton at a temp file and reset it afterwards."""
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps({"version": "1.0", "projects": []}))
    with patch.object(registry_module, "REGISTRY_FILE", registry_file):
        with patch.object(registry_module, "ensure_config_dirs"):
            registry_module._registry = None
            yield registry_module.get_registry()
            registry_module._registry = None


async def test_empty_state_then_add_reveals_layout(isolated_registry, tmp_path):
    from kata.tui.app import KataDashboard
    from kata.tui.widgets.tree import ProjectTree

    app = KataDashboard()
    async with app.run_test() as pilot:
        await pilot.pause()
        # Empty registry: EmptyState visible, main layout hidden.
        assert app.query_one("#empty-container").display is True
        assert app.query_one("#main-container").display is False

        # Add a project and simulate the wizard completing.
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        project = Project(name="proj", path=str(project_dir))
        isolated_registry.add(project)
        app._on_wizard_complete(project)

        await pilot.pause()
        await pilot.pause()

        # Main layout now visible, EmptyState hidden.
        assert app.query_one("#main-container").display is True
        assert app.query_one("#empty-container").display is False

        # The tree picked up the new project.
        tree = app.query_one(ProjectTree)
        assert "proj" in tree._projects_by_name
