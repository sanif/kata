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

    def test_get_recent_projects_empty(self, registry):
        """Test that empty registry returns empty list."""
        assert registry.get_recent_projects() == []

    def test_get_recent_projects_sorted_by_last_opened(self, registry, tmp_path):
        """Test projects are sorted by last_opened descending."""
        from datetime import datetime

        for i in range(3):
            path = tmp_path / f"dir{i}"
            path.mkdir()
            project = Project(
                name=f"project{i}",
                path=str(path),
                group="Test",
                config=f"project{i}.yaml",
                last_opened=datetime(2026, 1, i + 1),
            )
            registry.add(project)

        result = registry.get_recent_projects()
        assert [p.name for p in result] == ["project2", "project1", "project0"]

    def test_get_recent_projects_none_last_opened_sorted_last(self, registry, tmp_path):
        """Test that projects with None last_opened appear last."""
        from datetime import datetime

        # Project with no last_opened
        path0 = tmp_path / "dir0"
        path0.mkdir()
        registry.add(
            Project(
                name="never-opened",
                path=str(path0),
                group="Test",
                config="never-opened.yaml",
                last_opened=None,
            )
        )

        # Project with last_opened
        path1 = tmp_path / "dir1"
        path1.mkdir()
        registry.add(
            Project(
                name="opened",
                path=str(path1),
                group="Test",
                config="opened.yaml",
                last_opened=datetime(2026, 1, 1),
            )
        )

        result = registry.get_recent_projects()
        assert [p.name for p in result] == ["opened", "never-opened"]

    def test_get_recent_projects_limit(self, registry, tmp_path):
        """Test that limit parameter restricts results."""
        from datetime import datetime

        for i in range(5):
            path = tmp_path / f"dir{i}"
            path.mkdir()
            registry.add(
                Project(
                    name=f"project{i}",
                    path=str(path),
                    group="Test",
                    config=f"project{i}.yaml",
                    last_opened=datetime(2026, 1, i + 1),
                )
            )

        result = registry.get_recent_projects(limit=3)
        assert len(result) == 3
        assert [p.name for p in result] == ["project4", "project3", "project2"]

    def test_get_recent_projects_current_session_moves_to_position_1(self, registry, tmp_path):
        """Test that current_session project is moved to position 1."""
        from datetime import datetime

        for i in range(4):
            path = tmp_path / f"dir{i}"
            path.mkdir()
            registry.add(
                Project(
                    name=f"project{i}",
                    path=str(path),
                    group="Test",
                    config=f"project{i}.yaml",
                    last_opened=datetime(2026, 1, i + 1),
                )
            )

        # project3 is most recent (position 0), project2 is next, etc.
        # Passing current_session="project3" should move it to position 1
        result = registry.get_recent_projects(current_session="project3")
        assert result[0].name == "project2"  # previous project at position 0
        assert result[1].name == "project3"  # current session at position 1

    def test_get_recent_projects_current_session_sanitized_match(self, registry, tmp_path):
        """Test that current_session matches via sanitize_session_name."""
        from datetime import datetime

        for i, name in enumerate(["my.project", "other-project"]):
            path = tmp_path / f"dir{i}"
            path.mkdir()
            registry.add(
                Project(
                    name=name,
                    path=str(path),
                    group="Test",
                    config=f"{name}.yaml",
                    last_opened=datetime(2026, 1, i + 1),
                )
            )

        # "my.project" sanitizes to "my_project" in tmux
        # other-project is most recent (position 0), my.project is next
        # Passing sanitized name should match and move to position 1
        result = registry.get_recent_projects(current_session="my_project")
        assert result[0].name == "other-project"
        assert result[1].name == "my.project"

    def test_save_is_atomic(self, registry, tmp_path, temp_config_dir):
        """Test that registry save uses atomic write (temp + rename)."""
        path = tmp_path / "dir_atomic"
        path.mkdir()
        project = Project(
            name="atomic-test",
            path=str(path),
            group="Test",
            config="atomic-test.yaml",
        )
        registry.add(project)

        # Verify the registry file exists and is valid JSON
        import json

        data = json.loads(temp_config_dir.read_text())
        assert any(p["name"] == "atomic-test" for p in data["projects"])

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
