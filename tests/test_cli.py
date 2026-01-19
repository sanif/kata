"""Tests for CLI commands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kata.cli.app import app
from kata.core.models import Project, SessionStatus

runner = CliRunner()


@pytest.fixture
def temp_registry_file():
    """Create a temporary registry file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"version": "1.0", "projects": []}, f)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def mock_registry(temp_registry_file):
    """Set up mock registry and config directories."""
    with patch("kata.services.registry.REGISTRY_FILE", temp_registry_file):
        with patch("kata.services.registry.ensure_config_dirs"):
            with patch("kata.core.config.ensure_config_dirs"):
                # Reset singleton
                import kata.services.registry as reg_module
                reg_module._registry = None
                yield


class TestAddCommand:
    """Tests for 'kata add' command."""

    def test_add_current_directory(self, mock_registry, tmp_path):
        """Test adding current directory as project."""
        with patch("kata.cli.app.Path") as mock_path_class:
            mock_path_class.cwd.return_value = tmp_path
            mock_path_class.return_value = tmp_path

            result = runner.invoke(app, ["add", str(tmp_path)])

            assert result.exit_code == 0
            assert "Added project" in result.stdout

    def test_add_with_group(self, mock_registry, tmp_path):
        """Test adding project with group."""
        result = runner.invoke(app, ["add", str(tmp_path), "--group", "MyGroup"])

        assert result.exit_code == 0
        assert "MyGroup" in result.stdout

    def test_add_nonexistent_path(self, mock_registry, tmp_path):
        """Test adding nonexistent path fails."""
        nonexistent = tmp_path / "nonexistent"
        result = runner.invoke(app, ["add", str(nonexistent)])

        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_add_duplicate_path(self, mock_registry, tmp_path):
        """Test adding duplicate path fails."""
        # Add once
        result1 = runner.invoke(app, ["add", str(tmp_path)])
        assert result1.exit_code == 0

        # Add again - should fail
        result2 = runner.invoke(app, ["add", str(tmp_path)])
        assert result2.exit_code == 1
        assert "already exists" in result2.stdout


class TestListCommand:
    """Tests for 'kata list' command."""

    def test_list_empty(self, mock_registry):
        """Test listing when no projects registered."""
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No projects registered" in result.stdout

    def test_list_projects(self, mock_registry, tmp_path):
        """Test listing registered projects."""
        # Add a project first
        runner.invoke(app, ["add", str(tmp_path)])

        with patch("kata.cli.app.get_session_status", return_value=SessionStatus.IDLE):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert tmp_path.name in result.stdout

    def test_list_by_group(self, mock_registry, tmp_path):
        """Test listing projects filtered by group."""
        # Create subdirs for different projects
        path1 = tmp_path / "project1"
        path2 = tmp_path / "project2"
        path1.mkdir()
        path2.mkdir()

        runner.invoke(app, ["add", str(path1), "--group", "Group1"])
        runner.invoke(app, ["add", str(path2), "--group", "Group2"])

        with patch("kata.cli.app.get_session_status", return_value=SessionStatus.IDLE):
            result = runner.invoke(app, ["list", "--group", "Group1"])

        assert result.exit_code == 0
        assert "project1" in result.stdout


class TestRemoveCommand:
    """Tests for 'kata remove' command."""

    def test_remove_project(self, mock_registry, tmp_path):
        """Test removing a project."""
        runner.invoke(app, ["add", str(tmp_path)])

        result = runner.invoke(app, ["remove", tmp_path.name, "--force"])

        assert result.exit_code == 0
        assert "Removed project" in result.stdout

    def test_remove_nonexistent(self, mock_registry):
        """Test removing nonexistent project fails."""
        result = runner.invoke(app, ["remove", "nonexistent", "--force"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_remove_with_confirmation(self, mock_registry, tmp_path):
        """Test remove prompts for confirmation."""
        runner.invoke(app, ["add", str(tmp_path)])

        # Answer 'n' to confirmation
        result = runner.invoke(app, ["remove", tmp_path.name], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.stdout


class TestKillCommand:
    """Tests for 'kata kill' command."""

    def test_kill_requires_name_or_all(self, mock_registry):
        """Test kill requires either name or --all."""
        result = runner.invoke(app, ["kill"])

        assert result.exit_code == 1
        assert "Provide a session name or use --all" in result.stdout

    def test_kill_nonexistent_session(self, mock_registry, tmp_path):
        """Test killing nonexistent session fails."""
        runner.invoke(app, ["add", str(tmp_path)])

        with patch("kata.cli.app.session_exists", return_value=False):
            result = runner.invoke(app, ["kill", tmp_path.name, "--force"])

        assert result.exit_code == 1
        assert "No active session found" in result.stdout

    def test_kill_session(self, mock_registry, tmp_path):
        """Test killing an existing session."""
        runner.invoke(app, ["add", str(tmp_path)])

        with patch("kata.cli.app.session_exists", return_value=True):
            with patch("kata.cli.app.kill_session"):
                result = runner.invoke(app, ["kill", tmp_path.name, "--force"])

        assert result.exit_code == 0
        assert "Killed session" in result.stdout

    def test_kill_all_sessions(self, mock_registry, tmp_path):
        """Test killing all sessions."""
        path1 = tmp_path / "project1"
        path2 = tmp_path / "project2"
        path1.mkdir()
        path2.mkdir()

        runner.invoke(app, ["add", str(path1)])
        runner.invoke(app, ["add", str(path2)])

        with patch("kata.cli.app.get_all_kata_sessions", return_value=["project1", "project2"]):
            with patch("kata.cli.app.get_session_status", return_value=SessionStatus.ACTIVE):
                with patch("kata.cli.app.kill_session"):
                    result = runner.invoke(app, ["kill", "--all", "--force"])

        assert result.exit_code == 0
        assert "Killed 2 session(s)" in result.stdout


class TestScanCommand:
    """Tests for 'kata scan' command."""

    def test_scan_empty_directory(self, mock_registry, tmp_path):
        """Test scanning empty directory."""
        result = runner.invoke(app, ["scan", str(tmp_path)])

        assert result.exit_code == 0
        assert "No projects found" in result.stdout

    def test_scan_finds_projects(self, mock_registry, tmp_path):
        """Test scanning finds projects."""
        # Create a project with .git
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        result = runner.invoke(app, ["scan", str(tmp_path), "--yes"])

        assert result.exit_code == 0
        assert "Imported" in result.stdout

    def test_scan_filters_registered(self, mock_registry, tmp_path):
        """Test scan filters already-registered projects."""
        # Create and register a project
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        runner.invoke(app, ["add", str(project_dir)])

        # Scan should not find it as new
        result = runner.invoke(app, ["scan", str(tmp_path)])

        # Should indicate all are registered
        assert "all are already registered" in result.stdout or "No projects found" in result.stdout

    def test_scan_with_depth(self, mock_registry, tmp_path):
        """Test scan with custom depth."""
        # Create nested projects
        level1 = tmp_path / "level1"
        level2 = level1 / "level2"
        level2.mkdir(parents=True)
        (level2 / ".git").mkdir()

        # With depth 1, shouldn't find level2
        result = runner.invoke(app, ["scan", str(tmp_path), "--depth", "1"])

        # Level2 is at depth 2, so shouldn't be found with depth 1
        assert result.exit_code == 0


class TestMoveCommand:
    """Tests for 'kata move' command."""

    def test_move_project(self, mock_registry, tmp_path):
        """Test moving a project to new group."""
        runner.invoke(app, ["add", str(tmp_path), "--group", "OldGroup"])

        result = runner.invoke(app, ["move", tmp_path.name, "NewGroup"])

        assert result.exit_code == 0
        assert "Moved" in result.stdout
        assert "NewGroup" in result.stdout

    def test_move_nonexistent(self, mock_registry):
        """Test moving nonexistent project fails."""
        result = runner.invoke(app, ["move", "nonexistent", "NewGroup"])

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestLaunchCommand:
    """Tests for 'kata launch' command."""

    def test_launch_nonexistent(self, mock_registry):
        """Test launching nonexistent project fails."""
        result = runner.invoke(app, ["launch", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_launch_project(self, mock_registry, tmp_path):
        """Test launching a project."""
        runner.invoke(app, ["add", str(tmp_path)])

        with patch("kata.cli.app.launch_or_attach"):
            result = runner.invoke(app, ["launch", tmp_path.name])

        assert result.exit_code == 0
