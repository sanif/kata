"""TUI widgets for Kata dashboard."""

from kata.tui.widgets.preview import PreviewPane
from kata.tui.widgets.recents import RecentsPanel
from kata.tui.widgets.tree import ProjectTree

__all__ = [
    "ProjectTree",
    "RecentsPanel",
    "PreviewPane",
]
