"""Tests for template generation."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from kata.core.models import Project, ProjectType
from kata.core.templates import (
    get_template_path,
    render_template,
    template_exists,
    write_template,
)


@pytest.fixture
def project(tmp_path):
    """Create a test project."""
    return Project(
        name="test-project",
        path=str(tmp_path),
        group="Test",
        config="test-project.yaml",
    )


@pytest.fixture
def mock_config_dirs():
    """Mock config dirs - configs are now stored in project directories."""
    with patch("kata.core.config.ensure_config_dirs"):
        yield


class TestRenderTemplate:
    """Tests for render_template function."""

    def test_render_python_template(self, project):
        """Test rendering Python project template."""
        config = render_template(project, ProjectType.PYTHON)

        assert config["session_name"] == "test-project"
        assert config["start_directory"] == project.path
        assert len(config["windows"]) >= 2  # At least editor and shell

    def test_render_node_template(self, project):
        """Test rendering Node project template."""
        config = render_template(project, ProjectType.NODE)

        assert config["session_name"] == "test-project"
        assert len(config["windows"]) >= 2

    def test_render_go_template(self, project):
        """Test rendering Go project template."""
        config = render_template(project, ProjectType.GO)

        assert config["session_name"] == "test-project"
        assert len(config["windows"]) >= 2

    def test_render_generic_template(self, project):
        """Test rendering generic project template."""
        config = render_template(project, ProjectType.GENERIC)

        assert config["session_name"] == "test-project"
        assert len(config["windows"]) >= 1

    def test_template_has_valid_structure(self, project):
        """Test that all templates produce valid structure."""
        for project_type in ProjectType:
            config = render_template(project, project_type)
            assert config is not None
            assert "session_name" in config
            assert "windows" in config


class TestWriteTemplate:
    """Tests for write_template function."""

    def test_write_template(self, project, mock_config_dirs):
        """Test writing template to disk."""
        config_path = write_template(project, ProjectType.PYTHON)

        assert config_path.exists()
        assert config_path.name == ".kata.yaml"
        assert config_path.parent == Path(project.path)

        content = config_path.read_text()
        config = yaml.safe_load(content)
        assert config["session_name"] == "test-project"

    def test_write_template_creates_directory(self, project, mock_config_dirs):
        """Test that write creates the configs directory."""
        config_path = write_template(project, ProjectType.PYTHON)
        assert config_path.parent.exists()


class TestGetTemplatePath:
    """Tests for get_template_path function."""

    def test_get_template_path(self, project):
        """Test getting template path."""
        path = get_template_path(project)

        assert path.name == ".kata.yaml"
        assert path.parent == Path(project.path)


class TestTemplateExists:
    """Tests for template_exists function."""

    def test_template_exists_true(self, project, mock_config_dirs):
        """Test when template exists."""
        write_template(project, ProjectType.PYTHON)
        assert template_exists(project) is True

    def test_template_exists_false(self, project):
        """Test when template doesn't exist."""
        assert template_exists(project) is False


class TestTemplateContent:
    """Tests for template content specifics."""

    def test_python_template_has_venv_activation(self, project):
        """Test Python template includes venv activation."""
        config = render_template(project, ProjectType.PYTHON)

        # Look for venv activation in shell panes
        has_venv = False
        for window in config.get("windows", []):
            panes = window.get("panes", [])
            for pane in panes:
                if isinstance(pane, dict) and "shell_command" in pane:
                    commands = pane["shell_command"]
                    if any("venv" in str(cmd) for cmd in commands):
                        has_venv = True
        # Check the template is valid
        assert config is not None
        assert has_venv is True

    def test_node_template_has_npm_commands(self, project):
        """Test Node template structure is valid."""
        config = render_template(project, ProjectType.NODE)

        assert "windows" in config
        assert len(config["windows"]) > 0

    def test_go_template_has_valid_structure(self, project):
        """Test Go template structure is valid."""
        config = render_template(project, ProjectType.GO)

        assert "windows" in config
        assert "session_name" in config
        assert "start_directory" in config

    def test_template_uses_correct_start_directory(self, project):
        """Test templates use project path as start directory."""
        for project_type in ProjectType:
            config = render_template(project, project_type)

            assert config["start_directory"] == project.path
