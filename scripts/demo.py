#!/usr/bin/env python3
"""Launch Kata TUI with mock data for demo/video recording.

Usage:
    python scripts/demo.py

This starts the real interactive TUI with fake projects so you can
record a demo without exposing personal data. All keyboard shortcuts
work: Ctrl+Space, m, s, n, /, etc.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from kata.core.models import Project, ProjectType, SessionStatus

MOCK_PROJECTS = [
    Project(
        name="api-gateway",
        path="/home/dev/work/api-gateway",
        group="Work",
        config="api-gateway.yaml",
        created_at=datetime(2025, 6, 15),
        last_opened=datetime.now() - timedelta(minutes=12),
        times_opened=128,
        shortcut=1,
        color="cyan",
    ),
    Project(
        name="dashboard-ui",
        path="/home/dev/work/dashboard-ui",
        group="Work",
        config="dashboard-ui.yaml",
        created_at=datetime(2025, 8, 3),
        last_opened=datetime.now() - timedelta(hours=2),
        times_opened=87,
        shortcut=2,
        color="purple",
    ),
    Project(
        name="ml-pipeline",
        path="/home/dev/work/ml-pipeline",
        group="Work",
        config="ml-pipeline.yaml",
        created_at=datetime(2025, 9, 20),
        last_opened=datetime.now() - timedelta(hours=5),
        times_opened=45,
        shortcut=3,
        color="orange",
    ),
    Project(
        name="auth-service",
        path="/home/dev/work/auth-service",
        group="Work",
        config="auth-service.yaml",
        created_at=datetime(2025, 11, 1),
        last_opened=datetime.now() - timedelta(days=1),
        times_opened=62,
        color="green",
    ),
    Project(
        name="mobile-app",
        path="/home/dev/work/mobile-app",
        group="Work",
        config="mobile-app.yaml",
        created_at=datetime(2026, 1, 10),
        last_opened=datetime.now() - timedelta(days=2),
        times_opened=33,
        color="rose",
    ),
    Project(
        name="dotfiles",
        path="/home/dev/personal/dotfiles",
        group="Personal",
        config="dotfiles.yaml",
        created_at=datetime(2024, 3, 1),
        last_opened=datetime.now() - timedelta(days=3),
        times_opened=210,
        shortcut=9,
        color="teal",
    ),
    Project(
        name="blog",
        path="/home/dev/personal/blog",
        group="Personal",
        config="blog.yaml",
        created_at=datetime(2025, 5, 20),
        last_opened=datetime.now() - timedelta(days=7),
        times_opened=18,
        color="amber",
    ),
    Project(
        name="kata",
        path="/home/dev/oss/kata",
        group="Open Source",
        config="kata.yaml",
        created_at=datetime(2025, 2, 1),
        last_opened=datetime.now() - timedelta(minutes=30),
        times_opened=340,
        shortcut=4,
        color="blue",
    ),
]

MOCK_STATUSES = {
    "api-gateway": SessionStatus.ACTIVE,
    "dashboard-ui": SessionStatus.ACTIVE,
    "ml-pipeline": SessionStatus.DETACHED,
    "auth-service": SessionStatus.DETACHED,
    "kata": SessionStatus.ACTIVE,
    "dotfiles": SessionStatus.DETACHED,
}

MOCK_TYPES = {
    "/home/dev/work/api-gateway": ProjectType.GO,
    "/home/dev/work/dashboard-ui": ProjectType.NODE,
    "/home/dev/work/ml-pipeline": ProjectType.PYTHON,
    "/home/dev/work/auth-service": ProjectType.GO,
    "/home/dev/work/mobile-app": ProjectType.NODE,
    "/home/dev/personal/dotfiles": ProjectType.GENERIC,
    "/home/dev/personal/blog": ProjectType.NODE,
    "/home/dev/oss/kata": ProjectType.PYTHON,
}

MOCK_GIT = {
    "/home/dev/work/api-gateway": MagicMock(branch="main", is_dirty=False, ahead=0, behind=0),
    "/home/dev/work/dashboard-ui": MagicMock(
        branch="feat/charts", is_dirty=True, ahead=3, behind=0
    ),
    "/home/dev/work/ml-pipeline": MagicMock(
        branch="experiment/v2", is_dirty=True, ahead=1, behind=2
    ),
    "/home/dev/work/auth-service": MagicMock(branch="main", is_dirty=False, ahead=0, behind=0),
    "/home/dev/work/mobile-app": MagicMock(branch="develop", is_dirty=True, ahead=5, behind=0),
    "/home/dev/personal/dotfiles": MagicMock(branch="main", is_dirty=False, ahead=0, behind=0),
    "/home/dev/personal/blog": MagicMock(branch="main", is_dirty=False, ahead=0, behind=0),
    "/home/dev/oss/kata": MagicMock(
        branch="feature/notifications", is_dirty=True, ahead=12, behind=0
    ),
}


class MockRegistry:
    def __init__(self):
        self._projects = {p.name: p for p in MOCK_PROJECTS}

    def list_all(self):
        return list(self._projects.values())

    def get(self, name):
        return self._projects.get(name)

    def get_groups(self):
        return sorted({p.group for p in self._projects.values()})

    def list_by_group(self, group):
        return [p for p in self._projects.values() if p.group == group]

    def find_by_path(self, path):
        for p in self._projects.values():
            if p.path == str(path):
                return p
        return None

    def get_recent_projects(self, limit=5, current_session=None):
        sorted_p = sorted(
            self._projects.values(), key=lambda p: p.last_opened or datetime.min, reverse=True
        )
        return sorted_p[:limit]

    def reload(self):
        pass

    def update(self, project):
        self._projects[project.name] = project

    def __len__(self):
        return len(self._projects)

    def __contains__(self, name):
        return name in self._projects


def main():
    mock_reg = MockRegistry()

    patches = [
        patch("kata.services.registry.get_registry", return_value=mock_reg),
        patch("kata.services.registry._registry", mock_reg),
        patch("kata.tui.widgets.tree.get_registry", return_value=mock_reg),
        patch("kata.tui.widgets.tree.get_all_session_statuses", return_value=MOCK_STATUSES),
        patch("kata.tui.widgets.tree.get_git_status", lambda p: MOCK_GIT.get(str(p))),
        patch(
            "kata.tui.widgets.tree.detect_project_type",
            lambda p: MOCK_TYPES.get(str(p), ProjectType.GENERIC),
        ),
        patch("kata.tui.widgets.recents.query_zoxide", return_value=[]),
        patch("kata.tui.app.get_registry", return_value=mock_reg),
        # Prevent actual tmux session launches
        patch("kata.services.sessions.launch_or_attach", lambda p: None),
        patch("kata.services.sessions.launch_or_attach_adhoc", lambda d: None),
        patch("kata.services.sessions.kill_session", lambda n: None),
    ]

    for p in patches:
        p.start()

    try:
        from kata.tui.app import KataDashboard

        app = KataDashboard()
        app.run()
    finally:
        for p in patches:
            p.stop()


if __name__ == "__main__":
    main()
