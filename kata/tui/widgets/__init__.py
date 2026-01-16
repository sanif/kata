"""TUI widgets for Kata dashboard."""

from kata.tui.widgets.layout import LayoutDiagram
from kata.tui.widgets.preview import PreviewPane
from kata.tui.widgets.recents import RecentsPanel
from kata.tui.widgets.status import StatusIndicator
from kata.tui.widgets.tree import ProjectTree

__all__ = [
    "StatusIndicator",
    "ProjectTree",
    "RecentsPanel",
    "PreviewPane",
    "LayoutDiagram",
]
