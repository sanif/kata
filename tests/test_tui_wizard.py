"""Tests for the Add Project wizard's crash-safe add flow (item C).

These avoid mounting the full wizard (its DirectoryTree scans $HOME) by stubbing
the step widgets that ``_add_project`` queries.
"""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

import kata.services.registry as registry_module
from kata.core.models import ProjectType
from kata.core.templates import LayoutPreset
from kata.services.registry import DuplicatePathError


@pytest.fixture
def isolated_registry(tmp_path):
    registry_file = tmp_path / "registry.json"
    registry_file.write_text(json.dumps({"version": "1.0", "projects": []}))
    with patch.object(registry_module, "REGISTRY_FILE", registry_file):
        with patch.object(registry_module, "ensure_config_dirs"):
            registry_module._registry = None
            yield registry_module.get_registry()
            registry_module._registry = None


def _make_wizard(project_dir, layout=LayoutPreset.STANDARD):
    """Build an unmounted AddWizard with stubbed step widgets."""
    from kata.tui.screens.wizard import AddWizard

    wizard = AddWizard()
    wizard._path = project_dir
    wizard._group = "Test"
    wizard._show_error = MagicMock()
    wizard.dismiss = MagicMock()

    template_step = MagicMock()
    template_step.get_template.return_value = ProjectType.GENERIC
    layout_step = MagicMock()
    layout_step.get_layout.return_value = layout

    def fake_query_one(selector, *_a, **_k):
        if selector == "#template-step":
            return template_step
        if selector == "#layout-step":
            return layout_step
        raise AssertionError(f"unexpected query_one: {selector}")

    wizard.query_one = fake_query_one
    return wizard


@contextmanager
def _mock_app(wizard):
    from kata.tui.screens.wizard import AddWizard

    with patch.object(AddWizard, "app", new_callable=PropertyMock) as app_prop:
        app_prop.return_value = MagicMock()
        yield


def test_add_writes_config_before_registry(isolated_registry, tmp_path):
    from kata.core.config import get_project_config_path

    project_dir = tmp_path / "proj"
    project_dir.mkdir()

    wizard = _make_wizard(project_dir)
    with _mock_app(wizard):
        wizard._add_project()

    assert len(isolated_registry) == 1
    assert get_project_config_path(project_dir).exists()
    wizard.dismiss.assert_called_once()


def test_add_rolls_back_config_when_registry_fails(isolated_registry, tmp_path):
    from kata.core.config import get_project_config_path

    project_dir = tmp_path / "proj2"
    project_dir.mkdir()

    wizard = _make_wizard(project_dir)
    with _mock_app(wizard):
        with patch.object(isolated_registry, "add", side_effect=DuplicatePathError("dup")):
            wizard._add_project()

    # Registry stayed empty and the config we wrote was rolled back.
    assert len(isolated_registry) == 0
    assert not get_project_config_path(project_dir).exists()
    wizard._show_error.assert_called()
    wizard.dismiss.assert_not_called()


def test_add_surfaces_write_failure_without_registering(isolated_registry, tmp_path):
    project_dir = tmp_path / "proj3"
    project_dir.mkdir()

    wizard = _make_wizard(project_dir)
    with _mock_app(wizard):
        with patch(
            "kata.tui.screens.wizard.write_template",
            side_effect=OSError("read-only fs"),
        ):
            wizard._add_project()

    assert len(isolated_registry) == 0
    wizard._show_error.assert_called()
    wizard.dismiss.assert_not_called()
