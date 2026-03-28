#!/usr/bin/env python3
"""Capture screenshots of kata TUI with mock data for documentation.

Uses Textual's run_test() with mocked registry so no personal
project data is exposed in screenshots.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from kata.core.models import Project, SessionStatus

# ── Mock Data ────────────────────────────────────────────────────────────

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

# Simulate some sessions as active/detached
MOCK_STATUSES = {
    "api-gateway": SessionStatus.ACTIVE,
    "dashboard-ui": SessionStatus.ACTIVE,
    "ml-pipeline": SessionStatus.DETACHED,
    "auth-service": SessionStatus.DETACHED,
    "kata": SessionStatus.ACTIVE,
    "dotfiles": SessionStatus.DETACHED,
}


class MockRegistry:
    """Mock registry that returns fake projects."""

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

    def reload(self):
        pass

    def __len__(self):
        return len(self._projects)

    def __contains__(self, name):
        return name in self._projects


def _mock_git_status(path):
    """Return fake git status for mock projects."""
    statuses = {
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
    return statuses.get(str(path))


def _mock_detect_project_type(path):
    """Return fake project types."""
    from kata.core.models import ProjectType

    types = {
        "/home/dev/work/api-gateway": ProjectType.GO,
        "/home/dev/work/dashboard-ui": ProjectType.NODE,
        "/home/dev/work/ml-pipeline": ProjectType.PYTHON,
        "/home/dev/work/auth-service": ProjectType.GO,
        "/home/dev/work/mobile-app": ProjectType.NODE,
        "/home/dev/personal/dotfiles": ProjectType.GENERIC,
        "/home/dev/personal/blog": ProjectType.NODE,
        "/home/dev/oss/kata": ProjectType.PYTHON,
    }
    return types.get(str(path), ProjectType.GENERIC)


def _mock_session_statuses():
    return MOCK_STATUSES


def _mock_zoxide_entries():
    return []


# ── Capture Logic ────────────────────────────────────────────────────────


async def capture_screenshots(output_dir: Path = Path("screenshots")):
    """Capture all key screens with mock data."""
    output_dir.mkdir(exist_ok=True)

    mock_reg = MockRegistry()

    patches = [
        patch("kata.services.registry.get_registry", return_value=mock_reg),
        patch("kata.services.registry._registry", mock_reg),
        patch("kata.tui.widgets.tree.get_registry", return_value=mock_reg),
        patch("kata.tui.widgets.tree.get_all_session_statuses", _mock_session_statuses),
        patch("kata.tui.widgets.tree.get_git_status", _mock_git_status),
        patch("kata.tui.widgets.tree.detect_project_type", _mock_detect_project_type),
        patch("kata.tui.widgets.recents.query_zoxide", return_value=[]),
        patch("kata.tui.app.get_registry", return_value=mock_reg),
    ]

    for p in patches:
        p.start()

    try:
        from kata.tui.app import KataDashboard

        app = KataDashboard()
        async with app.run_test(size=(110, 35)) as pilot:
            await pilot.pause()
            await asyncio.sleep(0.5)

            # 1. Main dashboard
            app.save_screenshot(str(output_dir / "dashboard.svg"))
            print(f"  Saved: {output_dir / 'dashboard.svg'}")

            # 2. Settings
            await pilot.press("s")
            await pilot.pause()
            await asyncio.sleep(0.3)
            app.save_screenshot(str(output_dir / "settings.svg"))
            print(f"  Saved: {output_dir / 'settings.svg'}")
            await pilot.press("escape")
            await pilot.pause()

            # 3. Search
            await pilot.press("slash")
            await pilot.pause()
            await asyncio.sleep(0.3)
            app.save_screenshot(str(output_dir / "search.svg"))
            print(f"  Saved: {output_dir / 'search.svg'}")
            await pilot.press("escape")
            await pilot.pause()

            # 4. Context menu
            await pilot.press("m")
            await pilot.pause()
            await asyncio.sleep(0.3)
            app.save_screenshot(str(output_dir / "context_menu.svg"))
            print(f"  Saved: {output_dir / 'context_menu.svg'}")
            await pilot.press("escape")
            await pilot.pause()

            # 5. Notification center
            await pilot.press("n")
            await pilot.pause()
            await asyncio.sleep(0.3)
            app.save_screenshot(str(output_dir / "notifications.svg"))
            print(f"  Saved: {output_dir / 'notifications.svg'}")
            await pilot.press("escape")
            await pilot.pause()

            # 6. Help overlay
            await pilot.press("question_mark")
            await pilot.pause()
            await asyncio.sleep(0.3)
            app.save_screenshot(str(output_dir / "help.svg"))
            print(f"  Saved: {output_dir / 'help.svg'}")

    finally:
        for p in patches:
            p.stop()


if __name__ == "__main__":
    print("Capturing kata screenshots with mock data...")
    print()
    asyncio.run(capture_screenshots())
    print()
    print("Done! Screenshots saved to screenshots/")
