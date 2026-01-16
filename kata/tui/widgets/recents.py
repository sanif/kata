"""Recents panel widget for displaying zoxide entries."""

import os

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from kata.services.registry import get_registry
from kata.utils.detection import detect_project_type
from kata.utils.zoxide import ZoxideEntry, is_zoxide_available, query_zoxide

# Project type icons (Nerd Font)
PROJECT_TYPE_ICONS = {
    "python": "󰌠",
    "node": "󰎙",
    "rust": "󱘗",
    "go": "󰟓",
    "ruby": "󰴭",
    "generic": "󰉋",
}


class RecentItem(Static):
    """A single recent directory item."""

    DEFAULT_CSS = """
    RecentItem {
        width: auto;
        height: 3;
        min-width: 20;
        max-width: 40;
        padding: 0 2;
        margin: 0 1;
        background: $surface;
        content-align: center middle;
    }

    RecentItem:hover {
        background: $surface-lighten-1;
    }

    RecentItem.-selected {
        background: $primary 30%;
        border: tall $primary;
    }

    RecentItem.-focused {
        background: $primary 40%;
        border: tall $primary;
    }
    """

    def __init__(self, entry: ZoxideEntry, index: int) -> None:
        """Initialize recent item."""
        super().__init__()
        self.entry = entry
        self.index = index

    def compose(self):
        """Compose the item."""
        project_type = detect_project_type(self.entry.path)
        type_icon = PROJECT_TYPE_ICONS.get(project_type.value, PROJECT_TYPE_ICONS["generic"])

        # Shorten path
        display_path = self.entry.path
        home = os.path.expanduser("~")
        if display_path.startswith(home):
            display_path = "~" + display_path[len(home):]

        # Truncate path if too long
        if len(display_path) > 30:
            display_path = "..." + display_path[-27:]

        yield Static(
            f"[yellow]{type_icon}[/yellow] [bold]{self.entry.name}[/bold]\n"
            f"[dim]{display_path}[/dim]",
            markup=True,
        )


class RecentsPanel(Widget, can_focus=True):
    """Panel showing recent directories from zoxide."""

    DEFAULT_CSS = """
    RecentsPanel {
        width: 100%;
        height: 100%;
        background: $surface;
        border-top: tall $surface-lighten-1;
    }

    RecentsPanel #recents-header {
        width: 100%;
        height: 1;
        padding: 0 2;
        background: $surface;
    }

    RecentsPanel #recents-scroll {
        width: 100%;
        height: 1fr;
        padding: 0 1;
        overflow-x: auto;
        overflow-y: hidden;
    }

    RecentsPanel #recents-empty {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("a", "add_selected", "Add", show=False),
        Binding("left", "prev_item", "Previous", show=False),
        Binding("right", "next_item", "Next", show=False),
        Binding("h", "prev_item", "Previous", show=False),
        Binding("l", "next_item", "Next", show=False),
        Binding("enter", "select_item", "Select", show=False),
    ]

    class RecentSelected(Message, bubble=True):
        """Message sent when a recent entry is selected."""

        def __init__(self, entry: ZoxideEntry) -> None:
            super().__init__()
            self.entry = entry

    class RecentHighlighted(Message, bubble=True):
        """Message sent when a recent entry is highlighted."""

        def __init__(self, entry: ZoxideEntry) -> None:
            super().__init__()
            self.entry = entry

    class AddRequested(Message, bubble=True):
        """Message sent when user wants to add the selected entry as a project."""

        def __init__(self, entry: ZoxideEntry) -> None:
            super().__init__()
            self.entry = entry

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the recents panel."""
        super().__init__(name=name, id=id, classes=classes)
        self._entries: list[ZoxideEntry] = []
        self._selected_index: int = 0

    def compose(self):
        """Compose the widget."""
        yield Static(
            "[yellow]󰋚[/yellow] [dim]recents[/dim]  "
            "[dim]←→: navigate · a: add · Enter: open[/dim]",
            id="recents-header",
        )
        yield Horizontal(id="recents-scroll")

    def on_mount(self) -> None:
        """Load recents on mount."""
        self.refresh_recents()

    def refresh_recents(self) -> None:
        """Refresh the recents list from zoxide."""
        scroll = self.query_one("#recents-scroll", Horizontal)
        scroll.remove_children()
        self._entries.clear()

        if not is_zoxide_available():
            scroll.mount(Static("[dim]zoxide not available[/dim]", id="recents-empty"))
            return

        # Get registered project paths to exclude
        registry = get_registry()
        registered_paths = {p.path for p in registry.list_all()}

        # Query zoxide entries
        entries = query_zoxide(limit=20, exclude_paths=registered_paths)

        if not entries:
            scroll.mount(Static("[dim]No recent directories[/dim]", id="recents-empty"))
            return

        self._entries = entries
        self._selected_index = 0

        # Create items
        for i, entry in enumerate(entries):
            item = RecentItem(entry, i)
            if i == 0:
                item.add_class("-selected")
            scroll.mount(item)

    def _update_selection(self) -> None:
        """Update visual selection state."""
        items = self.query(RecentItem)
        for item in items:
            item.remove_class("-selected")
            item.remove_class("-focused")

        if 0 <= self._selected_index < len(self._entries):
            try:
                selected = list(items)[self._selected_index]
                if self.has_focus:
                    selected.add_class("-focused")
                else:
                    selected.add_class("-selected")
                selected.scroll_visible()

                # Update preview
                entry = self._entries[self._selected_index]
                self.post_message(self.RecentHighlighted(entry))
                try:
                    from kata.tui.widgets.preview import PreviewPane
                    preview = self.app.query_one(PreviewPane)
                    preview.update_zoxide(entry)
                except Exception:
                    pass
            except (IndexError, Exception):
                pass

    def on_focus(self) -> None:
        """Handle focus."""
        self._update_selection()

    def on_blur(self) -> None:
        """Handle blur."""
        self._update_selection()

    def action_prev_item(self) -> None:
        """Select previous item."""
        if self._entries and self._selected_index > 0:
            self._selected_index -= 1
            self._update_selection()

    def action_next_item(self) -> None:
        """Select next item."""
        if self._entries and self._selected_index < len(self._entries) - 1:
            self._selected_index += 1
            self._update_selection()

    def action_select_item(self) -> None:
        """Select current item."""
        entry = self.get_selected_entry()
        if entry:
            self.post_message(self.RecentSelected(entry))

    def get_selected_entry(self) -> ZoxideEntry | None:
        """Get the currently selected zoxide entry."""
        if 0 <= self._selected_index < len(self._entries):
            return self._entries[self._selected_index]
        return None

    def focus_list(self) -> None:
        """Focus the recents panel for keyboard navigation."""
        self.focus()

    def action_add_selected(self) -> None:
        """Request to add the selected entry as a project."""
        entry = self.get_selected_entry()
        if entry:
            self.post_message(self.AddRequested(entry))

    def filter_recents(self, query: str) -> None:
        """Filter recents by search query."""
        # For now, just refresh - filtering can be added later
        pass
