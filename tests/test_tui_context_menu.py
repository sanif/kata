"""Tests for TUI context-menu actions (rename flow) and the rename helper."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import yaml

import kata.services.registry as registry_module
from kata.core.models import Project
from kata.services.sessions import SessionError, rename_session


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


class TestRenameSession:
    """Tests for the rename_session tmux helper."""

    def test_rename_uses_exact_target(self):
        with patch("kata.services.sessions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            rename_session("old", "new")
            args = mock_run.call_args[0][0]
            assert args == ["tmux", "rename-session", "-t", "=old", "new"]

    def test_rename_raises_on_failure(self):
        with patch("kata.services.sessions.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="duplicate session: new")
            with pytest.raises(SessionError):
                rename_session("old", "new")


@contextmanager
def _mock_app(screen):
    """Give a bare screen instance a mock ``app`` (a read-only property)."""
    from kata.tui.screens.context_menu import ContextMenuScreen

    screen.dismiss = MagicMock()
    with patch.object(ContextMenuScreen, "app", new_callable=PropertyMock) as app_prop:
        app_prop.return_value = MagicMock()
        yield


class TestContextMenuRename:
    """Tests for the rename flow in ContextMenuScreen."""

    def _make_project(self, tmp_path, name="alpha"):
        project_dir = tmp_path / name
        project_dir.mkdir()
        # Write a .kata.yaml with a session_name key so we can verify the rewrite.
        (project_dir / ".kata.yaml").write_text(yaml.dump({"session_name": name, "windows": []}))
        return Project(name=name, path=str(project_dir))

    def test_rename_updates_registry_and_config(self, isolated_registry, tmp_path):
        from kata.tui.screens.context_menu import ContextMenuScreen

        project = self._make_project(tmp_path, "alpha")
        isolated_registry.add(project)

        screen = ContextMenuScreen(project)

        # No live tmux session, so no rename_session call is attempted.
        with _mock_app(screen):
            with patch("kata.tui.screens.context_menu.session_exists", return_value=False):
                screen._on_rename_input("beta")

        # Registry: old name gone, new name present.
        assert "beta" in isolated_registry
        assert "alpha" not in isolated_registry
        # Config: session_name rewritten to the sanitized new name.
        config = yaml.safe_load((tmp_path / "alpha" / ".kata.yaml").read_text())
        assert config["session_name"] == "beta"
        screen.dismiss.assert_called_once_with("renamed")

    def test_rename_renames_live_session(self, isolated_registry, tmp_path):
        from kata.tui.screens.context_menu import ContextMenuScreen

        project = self._make_project(tmp_path, "alpha")
        isolated_registry.add(project)

        screen = ContextMenuScreen(project)

        with _mock_app(screen):
            with (
                patch("kata.tui.screens.context_menu.session_exists", return_value=True),
                patch("kata.tui.screens.context_menu.rename_session") as mock_rename,
            ):
                screen._on_rename_input("beta")

        mock_rename.assert_called_once_with("alpha", "beta")
        assert "beta" in isolated_registry

    def test_rename_rolls_back_on_session_failure(self, isolated_registry, tmp_path):
        from kata.tui.screens.context_menu import ContextMenuScreen

        project = self._make_project(tmp_path, "alpha")
        isolated_registry.add(project)

        screen = ContextMenuScreen(project)

        with _mock_app(screen):
            with (
                patch("kata.tui.screens.context_menu.session_exists", return_value=True),
                patch(
                    "kata.tui.screens.context_menu.rename_session",
                    side_effect=SessionError("boom"),
                ),
            ):
                screen._on_rename_input("beta")

        # Registry rolled back to the original name.
        assert "alpha" in isolated_registry
        assert "beta" not in isolated_registry
        # Config restored.
        config = yaml.safe_load((tmp_path / "alpha" / ".kata.yaml").read_text())
        assert config["session_name"] == "alpha"
        screen.dismiss.assert_called_once_with(None)

    def test_rename_rejects_duplicate_name(self, isolated_registry, tmp_path):
        from kata.tui.screens.context_menu import ContextMenuScreen

        project = self._make_project(tmp_path, "alpha")
        other = self._make_project(tmp_path, "beta")
        isolated_registry.add(project)
        isolated_registry.add(other)

        screen = ContextMenuScreen(project)

        with _mock_app(screen):
            screen._on_rename_input("beta")

        # Nothing changed; both still present under original names.
        assert "alpha" in isolated_registry
        assert "beta" in isolated_registry
        screen.dismiss.assert_not_called()
