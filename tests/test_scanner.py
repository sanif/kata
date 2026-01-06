"""Tests for directory scanner."""

import pytest

from kata.utils.scanner import (
    SKIP_DIRECTORIES,
    get_project_info,
    is_project_directory,
    scan_directory,
)


class TestIsProjectDirectory:
    """Tests for is_project_directory function."""

    def test_git_directory(self, tmp_path):
        """Test detection of .git directory."""
        (tmp_path / ".git").mkdir()
        assert is_project_directory(tmp_path) is True

    def test_pyproject_toml(self, tmp_path):
        """Test detection of pyproject.toml."""
        (tmp_path / "pyproject.toml").touch()
        assert is_project_directory(tmp_path) is True

    def test_package_json(self, tmp_path):
        """Test detection of package.json."""
        (tmp_path / "package.json").touch()
        assert is_project_directory(tmp_path) is True

    def test_go_mod(self, tmp_path):
        """Test detection of go.mod."""
        (tmp_path / "go.mod").touch()
        assert is_project_directory(tmp_path) is True

    def test_setup_py(self, tmp_path):
        """Test detection of setup.py."""
        (tmp_path / "setup.py").touch()
        assert is_project_directory(tmp_path) is True

    def test_requirements_txt(self, tmp_path):
        """Test detection of requirements.txt."""
        (tmp_path / "requirements.txt").touch()
        assert is_project_directory(tmp_path) is True

    def test_empty_directory(self, tmp_path):
        """Test empty directory is not a project."""
        assert is_project_directory(tmp_path) is False

    def test_file_path(self, tmp_path):
        """Test file path is not a project."""
        file_path = tmp_path / "file.txt"
        file_path.touch()
        assert is_project_directory(file_path) is False


class TestScanDirectory:
    """Tests for scan_directory function."""

    def test_scan_empty_directory(self, tmp_path):
        """Test scanning empty directory."""
        projects = scan_directory(tmp_path)
        assert projects == []

    def test_scan_single_project(self, tmp_path):
        """Test scanning directory with single project."""
        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        projects = scan_directory(tmp_path)
        assert len(projects) == 1
        assert projects[0] == project_dir

    def test_scan_multiple_projects(self, tmp_path):
        """Test scanning directory with multiple projects."""
        for name in ["project1", "project2", "project3"]:
            project_dir = tmp_path / name
            project_dir.mkdir()
            (project_dir / ".git").mkdir()

        projects = scan_directory(tmp_path)
        assert len(projects) == 3

    def test_scan_nested_projects(self, tmp_path):
        """Test scanning nested project directories."""
        # Top-level project
        top_project = tmp_path / "top-project"
        top_project.mkdir()
        (top_project / ".git").mkdir()

        # Nested project (should NOT be found - we don't recurse into projects)
        nested = top_project / "nested-project"
        nested.mkdir()
        (nested / ".git").mkdir()

        projects = scan_directory(tmp_path)
        assert len(projects) == 1
        assert projects[0] == top_project

    def test_scan_respects_depth(self, tmp_path):
        """Test scanning respects max depth."""
        # Create project at depth 3
        level1 = tmp_path / "level1"
        level2 = level1 / "level2"
        level3 = level2 / "level3"
        level3.mkdir(parents=True)
        (level3 / ".git").mkdir()

        # With depth 2, shouldn't find it
        projects = scan_directory(tmp_path, max_depth=2)
        assert len(projects) == 0

        # With depth 3, should find it
        projects = scan_directory(tmp_path, max_depth=3)
        assert len(projects) == 1

    def test_scan_skips_hidden_directories(self, tmp_path):
        """Test scanning skips hidden directories by default."""
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / ".git").mkdir()

        projects = scan_directory(tmp_path)
        assert len(projects) == 0

    def test_scan_includes_hidden_when_enabled(self, tmp_path):
        """Test scanning includes hidden directories when enabled."""
        hidden = tmp_path / ".hidden-project"
        hidden.mkdir()
        (hidden / ".git").mkdir()

        projects = scan_directory(tmp_path, include_hidden=True)
        assert len(projects) == 1

    def test_scan_skips_node_modules(self, tmp_path):
        """Test scanning skips node_modules."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "package.json").touch()

        node_modules = project / "node_modules"
        node_modules.mkdir()

        # Even with .git in node_modules, shouldn't be found
        nested = node_modules / "some-package"
        nested.mkdir()
        (nested / "package.json").touch()

        projects = scan_directory(tmp_path)
        assert len(projects) == 1
        assert projects[0] == project

    def test_scan_skips_venv(self, tmp_path):
        """Test scanning skips .venv directory."""
        project = tmp_path / "project"
        project.mkdir()
        (project / "pyproject.toml").touch()

        venv = project / ".venv"
        venv.mkdir()
        (venv / "pyproject.toml").touch()

        projects = scan_directory(tmp_path)
        assert len(projects) == 1
        assert projects[0] == project

    def test_scan_returns_sorted_paths(self, tmp_path):
        """Test scanning returns sorted paths."""
        for name in ["z-project", "a-project", "m-project"]:
            project_dir = tmp_path / name
            project_dir.mkdir()
            (project_dir / ".git").mkdir()

        projects = scan_directory(tmp_path)
        names = [p.name for p in projects]
        assert names == ["a-project", "m-project", "z-project"]

    def test_scan_root_is_project(self, tmp_path):
        """Test scanning when root itself is a project."""
        (tmp_path / ".git").mkdir()

        projects = scan_directory(tmp_path)
        assert len(projects) == 1
        assert projects[0] == tmp_path


class TestGetProjectInfo:
    """Tests for get_project_info function."""

    def test_get_info_python_project(self, tmp_path):
        """Test getting info for Python project."""
        (tmp_path / "pyproject.toml").touch()
        (tmp_path / ".git").mkdir()

        info = get_project_info(tmp_path)

        assert info["name"] == tmp_path.name
        assert info["path"] == str(tmp_path)
        assert info["type"] == "python"
        assert info["has_git"] is True

    def test_get_info_node_project(self, tmp_path):
        """Test getting info for Node project."""
        (tmp_path / "package.json").touch()

        info = get_project_info(tmp_path)

        assert info["type"] == "node"
        assert info["has_git"] is False

    def test_get_info_generic_project(self, tmp_path):
        """Test getting info for generic project."""
        (tmp_path / ".git").mkdir()

        info = get_project_info(tmp_path)

        assert info["type"] == "generic"
        assert info["has_git"] is True


class TestSkipDirectories:
    """Tests for SKIP_DIRECTORIES constant."""

    def test_contains_common_excludes(self):
        """Test that common directories are in skip list."""
        expected = [
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            "dist",
            "build",
        ]
        for name in expected:
            assert name in SKIP_DIRECTORIES

    def test_all_strings(self):
        """Test all entries are strings."""
        for entry in SKIP_DIRECTORIES:
            assert isinstance(entry, str)
