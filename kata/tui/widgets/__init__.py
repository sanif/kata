"""TUI widgets for Kata dashboard."""

from kata.tui.widgets.layout import LayoutDiagram
from kata.tui.widgets.preview import PreviewPane
from kata.tui.widgets.search import SearchInput
from kata.tui.widgets.status import StatusIndicator
from kata.tui.widgets.tree import ProjectTree

__all__ = [
    "StatusIndicator",
    "ProjectTree",
    "SearchInput",
    "PreviewPane",
    "LayoutDiagram",
]
