"""Recents panel widget for displaying zoxide entries."""

from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, OptionList
from textual.widgets.option_list import Option

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


class RecentsPanel(Widget):
    """Panel showing recent directories from zoxide."""

    DEFAULT_CSS = """
    RecentsPanel {
        width: 100%;
        height: 100%;
        background: $background;
        border-top: solid $surface-lighten-1;
    }

    RecentsPanel #recents-header {
        width: 100%;
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }

    RecentsPanel #recents-list {
        width: 100%;
        height: 1fr;
        background: $background;
        padding: 0 1;
    }

    RecentsPanel #recents-list:focus {
        border: none;
    }

    RecentsPanel #recents-list > .option-list--option-highlighted {
        background: $surface;
    }

    RecentsPanel #recents-empty {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
    }
    """

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

    def compose(self):
        """Compose the widget."""
        yield Static("[dim]󰋚 recents[/dim]  [dim](Tab to switch)[/dim]", id="recents-header")
        yield OptionList(id="recents-list")

    def on_mount(self) -> None:
        """Load recents on mount."""
        self.refresh_recents()

    def refresh_recents(self) -> None:
        """Refresh the recents list from zoxide."""
        option_list = self.query_one("#recents-list", OptionList)
        option_list.clear_options()
        self._entries.clear()

        if not is_zoxide_available():
            option_list.add_option(Option("[dim]zoxide not available[/dim]", disabled=True))
            return

        # Get registered project paths to exclude
        registry = get_registry()
        registered_paths = {p.path for p in registry.list_all()}

        # Query zoxide entries
        entries = query_zoxide(limit=20, exclude_paths=registered_paths)

        if not entries:
            option_list.add_option(Option("[dim]No recent directories[/dim]", disabled=True))
            return

        self._entries = entries

        for entry in entries:
            project_type = detect_project_type(entry.path)
            type_icon = PROJECT_TYPE_ICONS.get(project_type.value, PROJECT_TYPE_ICONS["generic"])
            # Format: icon name (dimmed path)
            label = f"[yellow]{type_icon}[/yellow] {entry.name}  [dim]{entry.path}[/dim]"
            option_list.add_option(Option(label, id=entry.path))

    def get_selected_entry(self) -> ZoxideEntry | None:
        """Get the currently selected zoxide entry."""
        option_list = self.query_one("#recents-list", OptionList)
        idx = option_list.highlighted
        if idx is not None and 0 <= idx < len(self._entries):
            return self._entries[idx]
        return None

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection (Enter key)."""
        entry = self.get_selected_entry()
        if entry:
            self.post_message(self.RecentSelected(entry))

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Handle option highlight (cursor movement)."""
        entry = self.get_selected_entry()
        if entry:
            self.post_message(self.RecentHighlighted(entry))
            # Update preview pane
            try:
                from kata.tui.widgets.preview import PreviewPane
                preview = self.app.query_one(PreviewPane)
                preview.update_zoxide(entry)
            except Exception:
                pass

    def focus_list(self) -> None:
        """Focus the option list for keyboard navigation."""
        try:
            option_list = self.query_one("#recents-list", OptionList)
            option_list.focus()
        except Exception:
            pass
