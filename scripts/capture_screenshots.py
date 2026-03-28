#!/usr/bin/env python3
"""Capture screenshots of kata TUI with mock data for documentation.

Uses Textual's run_test() for TUI screens and Rich Console export
for popup strips (switch_strip, notify_strip).
"""

import asyncio
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console

from kata.core.models import Project, ProjectType, SessionStatus

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

    def __len__(self):
        return len(self._projects)

    def __contains__(self, name):
        return name in self._projects


# ── Rich Console → SVG export ───────────────────────────────────────────


def _rich_lines_to_svg(lines, width, title="kata", output_path=None):
    """Render Rich Text lines to SVG via Console.export_svg()."""
    console = Console(
        file=StringIO(),
        force_terminal=True,
        width=width,
        record=True,
        color_system="truecolor",
    )
    for line in lines:
        console.print(line, end="\n")

    svg = console.export_svg(title=title)
    if output_path:
        Path(output_path).write_text(svg)
    return svg


# ── Capture: Switch Strip ────────────────────────────────────────────────


def capture_switch_strip(output_dir: Path):
    """Capture the Ctrl+Space switcher popup."""
    from kata.cli.switch_strip import render_panel

    # Use projects that have active/detached sessions
    active_projects = [p for p in MOCK_PROJECTS if p.name in MOCK_STATUSES]
    w = max(len(p.name) for p in active_projects) + 16
    w = max(w, 37)

    lines = render_panel(
        projects=active_projects,
        statuses=MOCK_STATUSES,
        selected_index=1,
        current_session="api-gateway",
        term_width=w,
    )

    _rich_lines_to_svg(lines, w, title="switch", output_path=output_dir / "switcher.svg")
    print(f"  Saved: {output_dir / 'switcher.svg'}")


# ── Capture: Notify Strip ────────────────────────────────────────────────


def capture_notify_strip(output_dir: Path):
    """Capture the Ctrl+N notification popup."""

    from kata.cli.notify_strip import _build_projects, render_panel
    from kata.services.notifications.models import (
        Notification,
        NotificationSource,
        NotificationType,
    )

    # Build mock notifications grouped by session
    mock_notifications = {
        "api-gateway": [
            Notification(
                type=NotificationType.TASK_COMPLETE,
                source=NotificationSource.CLAUDE_CODE,
                title="Task Complete",
                body="Refactored authentication middleware with JWT validation",
                session_name="api-gateway",
                timestamp=datetime.now() - timedelta(minutes=5),
            ),
            Notification(
                type=NotificationType.QUESTION,
                source=NotificationSource.CLAUDE_CODE,
                title="Question",
                body="Should I add rate limiting to the /api/v2 endpoints?",
                session_name="api-gateway",
                timestamp=datetime.now() - timedelta(minutes=8),
            ),
        ],
        "dashboard-ui": [
            Notification(
                type=NotificationType.TASK_COMPLETE,
                source=NotificationSource.GEMINI,
                title="Task Complete",
                body="Chart component now supports real-time data streaming",
                session_name="dashboard-ui",
                timestamp=datetime.now() - timedelta(minutes=15),
            ),
        ],
        "kata": [
            Notification(
                type=NotificationType.PLAN_READY,
                source=NotificationSource.CLAUDE_CODE,
                title="Plan Ready",
                body="Implementation plan for notification sound system ready for review",
                session_name="kata",
                timestamp=datetime.now() - timedelta(minutes=30),
            ),
            Notification(
                type=NotificationType.TASK_COMPLETE,
                source=NotificationSource.CLAUDE_CODE,
                title="Task Complete",
                body="Added 6 sound packs with per-event audio mapping",
                session_name="kata",
                timestamp=datetime.now() - timedelta(hours=1),
            ),
            Notification(
                type=NotificationType.ERROR,
                source=NotificationSource.CLAUDE_CODE,
                title="Error",
                body="Test test_daemon_broadcast failed: asyncio.TimeoutError",
                session_name="kata",
                timestamp=datetime.now() - timedelta(hours=2),
            ),
        ],
    }

    projects = _build_projects(mock_notifications)
    w = 72
    content_rows = max(len(projects), max(len(v) for v in mock_notifications.values())) + 2
    content_rows = min(content_rows, 10)

    lines = render_panel(
        projects=projects,
        cursor=0,
        total_unread=6,
        grouped=mock_notifications,
        content_rows=content_rows,
    )

    _rich_lines_to_svg(lines, w, title="notifications", output_path=output_dir / "notify_popup.svg")
    print(f"  Saved: {output_dir / 'notify_popup.svg'}")


# ── Capture: TUI Screens ────────────────────────────────────────────────


async def capture_tui_screens(output_dir: Path):
    """Capture TUI dashboard and modal screens."""
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
    ]

    for p in patches:
        p.start()

    try:
        from kata.tui.app import KataDashboard

        app = KataDashboard()
        async with app.run_test(size=(110, 35)) as pilot:
            # Wait for tree to load
            await pilot.pause()
            await asyncio.sleep(1.0)

            # 1. Dashboard
            app.save_screenshot(str(output_dir / "dashboard.svg"))
            print(f"  Saved: {output_dir / 'dashboard.svg'}")

            # 2. Search
            await pilot.press("slash")
            await asyncio.sleep(0.5)
            app.save_screenshot(str(output_dir / "search.svg"))
            print(f"  Saved: {output_dir / 'search.svg'}")
            await pilot.press("escape")
            await asyncio.sleep(0.3)

            # 3. Settings
            await pilot.press("s")
            await asyncio.sleep(0.5)
            app.save_screenshot(str(output_dir / "settings.svg"))
            print(f"  Saved: {output_dir / 'settings.svg'}")
            await pilot.press("escape")
            await asyncio.sleep(0.3)

            # 4. Context menu — need to select a project first
            await pilot.press("down")  # Move into tree
            await asyncio.sleep(0.2)
            await pilot.press("m")
            await asyncio.sleep(0.5)
            app.save_screenshot(str(output_dir / "context_menu.svg"))
            print(f"  Saved: {output_dir / 'context_menu.svg'}")
            await pilot.press("escape")
            await asyncio.sleep(0.3)

            # 5. Notification center
            await pilot.press("n")
            await asyncio.sleep(0.5)
            app.save_screenshot(str(output_dir / "notifications.svg"))
            print(f"  Saved: {output_dir / 'notifications.svg'}")

    finally:
        for p in patches:
            p.stop()


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    output_dir = Path("screenshots")
    output_dir.mkdir(exist_ok=True)

    print("Capturing kata screenshots with mock data...")
    print()

    # Popup strips (Rich → SVG)
    print("[Popup strips]")
    capture_switch_strip(output_dir)
    capture_notify_strip(output_dir)
    print()

    # TUI screens (Textual → SVG)
    print("[TUI screens]")
    asyncio.run(capture_tui_screens(output_dir))
    print()

    print("Done! Screenshots saved to screenshots/")


if __name__ == "__main__":
    main()
