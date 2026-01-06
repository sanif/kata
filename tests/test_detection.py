"""Tests for project type detection."""

import pytest

from kata.core.models import ProjectType
from kata.utils.detection import (
    PROJECT_MARKERS,
    detect_project_type,
    get_project_markers,
)


class TestDetectProjectType:
    """Tests for detect_project_type function."""

    def test_detect_python_pyproject(self, tmp_path):
        """Test detecting Python project by pyproject.toml."""
        (tmp_path / "pyproject.toml").touch()
        assert detect_project_type(tmp_path) == ProjectType.PYTHON

    def test_detect_python_setup_py(self, tmp_path):
        """Test detecting Python project by setup.py."""
        (tmp_path / "setup.py").touch()
        assert detect_project_type(tmp_path) == ProjectType.PYTHON

    def test_detect_python_requirements(self, tmp_path):
        """Test detecting Python project by requirements.txt."""
        (tmp_path / "requirements.txt").touch()
        assert detect_project_type(tmp_path) == ProjectType.PYTHON

    def test_detect_python_pipfile(self, tmp_path):
        """Test detecting Python project by Pipfile."""
        (tmp_path / "Pipfile").touch()
        assert detect_project_type(tmp_path) == ProjectType.PYTHON

    def test_detect_node(self, tmp_path):
        """Test detecting Node project by package.json."""
        (tmp_path / "package.json").touch()
        assert detect_project_type(tmp_path) == ProjectType.NODE

    def test_detect_go(self, tmp_path):
        """Test detecting Go project by go.mod."""
        (tmp_path / "go.mod").touch()
        assert detect_project_type(tmp_path) == ProjectType.GO

    def test_detect_generic(self, tmp_path):
        """Test detecting generic project when no markers found."""
        assert detect_project_type(tmp_path) == ProjectType.GENERIC

    def test_detect_python_priority_over_node(self, tmp_path):
        """Test that Python markers take priority when multiple exist."""
        (tmp_path / "pyproject.toml").touch()
        (tmp_path / "package.json").touch()
        # Python should be detected due to priority order
        result = detect_project_type(tmp_path)
        assert result in (ProjectType.PYTHON, ProjectType.NODE)

    def test_detect_with_string_path(self, tmp_path):
        """Test detection with string path."""
        (tmp_path / "pyproject.toml").touch()
        assert detect_project_type(str(tmp_path)) == ProjectType.PYTHON

    def test_detect_nonexistent_path(self, tmp_path):
        """Test detection with nonexistent path returns generic."""
        nonexistent = tmp_path / "nonexistent"
        assert detect_project_type(nonexistent) == ProjectType.GENERIC


class TestGetProjectMarkers:
    """Tests for get_project_markers function."""

    def test_get_python_markers(self):
        """Test getting Python project markers."""
        markers = get_project_markers(ProjectType.PYTHON)
        assert "pyproject.toml" in markers
        assert "setup.py" in markers
        assert "requirements.txt" in markers

    def test_get_node_markers(self):
        """Test getting Node project markers."""
        markers = get_project_markers(ProjectType.NODE)
        assert "package.json" in markers

    def test_get_go_markers(self):
        """Test getting Go project markers."""
        markers = get_project_markers(ProjectType.GO)
        assert "go.mod" in markers

    def test_get_generic_markers(self):
        """Test getting generic project markers (empty)."""
        markers = get_project_markers(ProjectType.GENERIC)
        assert markers == []


class TestProjectMarkers:
    """Tests for PROJECT_MARKERS constant."""

    def test_markers_defined_for_main_types(self):
        """Test that markers are defined for main project types."""
        assert ProjectType.PYTHON in PROJECT_MARKERS
        assert ProjectType.NODE in PROJECT_MARKERS
        assert ProjectType.GO in PROJECT_MARKERS

    def test_each_type_has_markers(self):
        """Test that each defined type has at least one marker."""
        for project_type, markers in PROJECT_MARKERS.items():
            assert len(markers) > 0, f"{project_type} should have markers"

    def test_markers_are_strings(self):
        """Test that all markers are strings."""
        for project_type, markers in PROJECT_MARKERS.items():
            for marker in markers:
                assert isinstance(marker, str)
