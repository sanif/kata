"""Recents panel widget for displaying zoxide entries."""

import os

from textual.binding import Binding
from textual.message import Message
from textual.widget import Widget
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from kata.services.registry import get_registry
from kata.tui.icons import project_type_icon
from kata.utils.detection import detect_project_type
from kata.utils.zoxide import ZoxideEntry, is_zoxide_available, query_zoxide


class RecentsPanel(Widget, can_focus=True):
    """Panel showing recent directories from zoxide."""

    DEFAULT_CSS = """
    RecentsPanel {
        width: 100%;
        height: 100%;
        background: $background;
    }

    RecentsPanel #recents-header {
        width: 100%;
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }

    RecentsPanel #recents-list {
        width: 100%;
        height: 1fr;
        background: $background;
        scrollbar-size: 1 1;
        padding: 0 1;
    }

    RecentsPanel #recents-list:focus {
        background: $background;
    }

    RecentsPanel #recents-list > .option-list--option {
        padding: 0 1;
        background: $background;
    }

    RecentsPanel #recents-list > .option-list--option-highlighted {
        background: $surface-lighten-1;
    }

    RecentsPanel #recents-list:focus > .option-list--option-highlighted {
        background: $primary 22%;
    }
    """

    BINDINGS = [
        Binding("a", "add_selected", "Add", show=False),
    ]

    class RecentSelected(Message, bubble=True):
        """Message sent when a recent entry is selected."""

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
        # Cache of type icons keyed by path, computed once in the worker so
        # re-renders never touch the filesystem.
        self._icon_cache: dict[str, str] = {}

    def compose(self):
        """Compose the widget."""
        yield Static(
            "[bold $primary]󰋚[/bold $primary] [dim]Recent folders[/dim]",
            id="recents-header",
        )
        yield OptionList(id="recents-list")

    def on_mount(self) -> None:
        """Load recents on mount."""
        self.refresh_recents()

    def refresh_recents(self) -> None:
        """Refresh the recents list — zoxide query + type detection run in a worker."""

        def _work() -> None:
            if not is_zoxide_available():
                self.app.call_from_thread(self._render_message, "zoxide not available")
                return

            registry = get_registry()
            registered_paths = {p.path for p in registry.list_all()}
            entries = query_zoxide(limit=50, exclude_paths=registered_paths)

            if not entries:
                self.app.call_from_thread(self._render_message, "No recent directories")
                return

            # Compute type icons once here (filesystem I/O), off the UI thread.
            icons = {e.path: project_type_icon(detect_project_type(e.path).value) for e in entries}
            self.app.call_from_thread(self._apply_entries, entries, icons)

        self.run_worker(_work, thread=True, exclusive=True, group="recents")

    def _render_message(self, message: str) -> None:
        """Render a placeholder message (main thread)."""
        try:
            option_list = self.query_one("#recents-list", OptionList)
        except Exception:
            return
        option_list.clear_options()
        self._entries = []
        option_list.add_option(Option(f"[dim]{message}[/dim]", disabled=True))

    def _apply_entries(self, entries: list[ZoxideEntry], icons: dict[str, str]) -> None:
        """Apply computed entries to the list (main thread, no I/O)."""
        self._icon_cache = icons
        self._entries = entries
        self._render_entries(entries)

    def _render_entries(self, entries: list[ZoxideEntry]) -> None:
        """Render entries to the option list using cached icons (no I/O)."""
        try:
            option_list = self.query_one("#recents-list", OptionList)
        except Exception:
            return
        option_list.clear_options()
        self._entries = entries

        if not entries:
            option_list.add_option(Option("[dim]No matches[/dim]", disabled=True))
            return

        home = os.path.expanduser("~")

        for entry in entries:
            type_icon = self._icon_cache.get(entry.path) or project_type_icon("generic")

            # Shorten path for display (show ~/ for home)
            display_path = entry.path
            if display_path.startswith(home):
                display_path = "~" + display_path[len(home) :]

            # Format: icon name path
            label = f"[dim]{type_icon}[/dim] {entry.name}  [dim]{display_path}[/dim]"
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

    def action_add_selected(self) -> None:
        """Request to add the selected entry as a project."""
        entry = self.get_selected_entry()
        if entry:
            self.post_message(self.AddRequested(entry))
