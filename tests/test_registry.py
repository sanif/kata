"""Tests for registry service."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from kata.core.models import Project
from kata.services.registry import (
    DuplicatePathError,
    ProjectNotFoundError,
    Registry,
)


@pytest.fixture
def temp_registry_file():
    """Create a temporary registry file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"version": "1.0", "projects": []}, f)
        temp_path = Path(f.name)
    yield temp_path
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_config_dir(temp_registry_file):
    """Create patches for config directory."""
    with patch("kata.services.registry.REGISTRY_FILE", temp_registry_file):
        with patch("kata.services.registry.ensure_config_dirs"):
            yield temp_registry_file


@pytest.fixture
def registry(temp_config_dir):
    """Create a fresh registry instance."""
    return Registry()


class TestRegistry:
    """Test cases for Registry class."""

    def test_add_project(self, registry, tmp_path):
        """Test adding a project."""
        project = Project(
            name="test-project",
            path=str(tmp_path),
            group="Test",
            config="test-project.yaml",
        )

        registry.add(project)

        assert "test-project" in registry
        assert len(registry) == 1

    def test_add_duplicate_path_raises(self, registry, tmp_path):
        """Test that adding a project with duplicate path raises error."""
        project1 = Project(
            name="project1",
            path=str(tmp_path),
            group="Test",
            config="project1.yaml",
        )
        project2 = Project(
            name="project2",
            path=str(tmp_path),
            group="Test",
            config="project2.yaml",
        )

        registry.add(project1)

        with pytest.raises(DuplicatePathError):
            registry.add(project2)

    def test_add_with_name_collision_auto_renames(self, registry, tmp_path):
        """Test that name collisions are handled by auto-renaming."""
        path1 = tmp_path / "dir1"
        path2 = tmp_path / "dir2"
        path1.mkdir()
        path2.mkdir()

        project1 = Project(
            name="project",
            path=str(path1),
            group="Test",
            config="project.yaml",
        )
        project2 = Project(
            name="project",
            path=str(path2),
            group="Test",
            config="project.yaml",
        )

        registry.add(project1)
        registry.add(project2)

        assert "project" in registry
        assert "project-1" in registry
        assert len(registry) == 2

    def test_remove_project(self, registry, tmp_path):
        """Test removing a project."""
        project = Project(
            name="test-project",
            path=str(tmp_path),
            group="Test",
            config="test-project.yaml",
        )

        registry.add(project)
        removed = registry.remove("test-project")

        assert removed.name == "test-project"
        assert "test-project" not in registry
        assert len(registry) == 0

    def test_remove_nonexistent_raises(self, registry):
        """Test that removing nonexistent project raises error."""
        with pytest.raises(ProjectNotFoundError):
            registry.remove("nonexistent")

    def test_get_project(self, registry, tmp_path):
        """Test getting a project by name."""
        project = Project(
            name="test-project",
            path=str(tmp_path),
            group="Test",
            config="test-project.yaml",
        )

        registry.add(project)
        retrieved = registry.get("test-project")

        assert retrieved.name == "test-project"
        assert retrieved.path == str(tmp_path)

    def test_get_nonexistent_raises(self, registry):
        """Test that getting nonexistent project raises error."""
        with pytest.raises(ProjectNotFoundError):
            registry.get("nonexistent")

    def test_update_project(self, registry, tmp_path):
        """Test updating a project."""
        project = Project(
            name="test-project",
            path=str(tmp_path),
            group="Test",
            config="test-project.yaml",
        )

        registry.add(project)

        project.group = "Updated"
        registry.update(project)

        retrieved = registry.get("test-project")
        assert retrieved.group == "Updated"

    def test_update_nonexistent_raises(self, registry, tmp_path):
        """Test that updating nonexistent project raises error."""
        project = Project(
            name="nonexistent",
            path=str(tmp_path),
            group="Test",
            config="nonexistent.yaml",
        )

        with pytest.raises(ProjectNotFoundError):
            registry.update(project)

    def test_list_all(self, registry, tmp_path):
        """Test listing all projects."""
        for i in range(3):
            path = tmp_path / f"dir{i}"
            path.mkdir()
            project = Project(
                name=f"project{i}",
                path=str(path),
                group="Test",
                config=f"project{i}.yaml",
            )
            registry.add(project)

        projects = registry.list_all()
        assert len(projects) == 3

    def test_list_by_group(self, registry, tmp_path):
        """Test listing projects by group."""
        for i in range(3):
            path = tmp_path / f"dir{i}"
            path.mkdir()
            project = Project(
                name=f"project{i}",
                path=str(path),
                group="Group1" if i < 2 else "Group2",
                config=f"project{i}.yaml",
            )
            registry.add(project)

        group1_projects = registry.list_by_group("Group1")
        group2_projects = registry.list_by_group("Group2")

        assert len(group1_projects) == 2
        assert len(group2_projects) == 1

    def test_get_groups(self, registry, tmp_path):
        """Test getting all group names."""
        for i, group in enumerate(["Alpha", "Beta", "Alpha"]):
            path = tmp_path / f"dir{i}"
            path.mkdir()
            project = Project(
                name=f"project{i}",
                path=str(path),
                group=group,
                config=f"project{i}.yaml",
            )
            registry.add(project)

        groups = registry.get_groups()
        assert groups == ["Alpha", "Beta"]

    def test_find_by_path(self, registry, tmp_path):
        """Test finding a project by path."""
        project = Project(
            name="test-project",
            path=str(tmp_path),
            group="Test",
            config="test-project.yaml",
        )

        registry.add(project)
        found = registry.find_by_path(tmp_path)

        assert found is not None
        assert found.name == "test-project"

    def test_find_by_path_not_found(self, registry, tmp_path):
        """Test finding by path when not found."""
        found = registry.find_by_path(tmp_path)
        assert found is None

    def test_persistence(self, temp_config_dir, tmp_path):
        """Test that registry persists data across instances."""
        # Create first registry and add project
        registry1 = Registry()
        project = Project(
            name="test-project",
            path=str(tmp_path),
            group="Test",
            config="test-project.yaml",
        )
        registry1.add(project)

        # Create second registry and verify project exists
        registry2 = Registry()
        assert "test-project" in registry2
        assert len(registry2) == 1
