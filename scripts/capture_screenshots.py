#!/usr/bin/env python3
"""Capture screenshots of kata TUI for documentation."""

import asyncio
from pathlib import Path

from kata.tui.app import KataDashboard


async def capture_screenshots(output_dir: Path = Path("screenshots")):
    """Capture all key screens."""
    output_dir.mkdir(exist_ok=True)

    app = KataDashboard()
    async with app.run_test(size=(100, 30)) as pilot:
        # Wait for initial render
        await pilot.pause()

        # 1. Main dashboard
        app.save_screenshot(str(output_dir / "dashboard.svg"))

        # 2. Settings screen
        await pilot.press("s")
        await pilot.pause()
        app.save_screenshot(str(output_dir / "settings.svg"))
        await pilot.press("escape")
        await pilot.pause()

        # 3. Search modal
        await pilot.press("slash")
        await pilot.pause()
        app.save_screenshot(str(output_dir / "search.svg"))
        await pilot.press("escape")
        await pilot.pause()

        # 4. Context menu (needs project selected)
        await pilot.press("m")
        await pilot.pause()
        app.save_screenshot(str(output_dir / "context_menu.svg"))
        await pilot.press("escape")


if __name__ == "__main__":
    asyncio.run(capture_screenshots())
