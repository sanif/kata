"""Search modal screen for quick project/directory switching."""

from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from kata.core.models import Project, SessionStatus
from kata.services.registry import get_registry
from kata.services.sessions import get_all_session_statuses
from kata.tui.icons import project_type_icon, status_indicator
from kata.utils.detection import detect_project_type
from kata.utils.matching import fuzzy_match
from kata.utils.zoxide import ZoxideEntry, is_zoxide_available, query_zoxide


class SearchModal(ModalScreen[Project | ZoxideEntry | None]):
    """Modal search screen for quick switching."""

    DEFAULT_CSS = """
    SearchModal {
        align: center middle;
    }

    SearchModal #search-container {
        width: 75;
        height: 25;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 1 2;
    }

    SearchModal #search-header {
        width: 100%;
        height: 1;
        content-align: center middle;
        color: $text-muted;
        margin-bottom: 1;
    }

    SearchModal #search-input {
        width: 100%;
        height: 3;
        margin-bottom: 1;
    }

    SearchModal #search-input:focus {
        border: tall $primary;
    }

    SearchModal #search-results {
        width: 100%;
        height: 1fr;
        background: $surface;
    }

    SearchModal #search-results:focus {
        border: none;
    }

    SearchModal #search-results > .option-list--option-highlighted {
        background: $primary 25%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("enter", "select", "Select", show=False),
        Binding("down", "focus_results", "Down", show=False),
        Binding("up", "focus_results", "Up", show=False),
    ]

    def __init__(self) -> None:
        """Initialize the search modal."""
        super().__init__()
        self._projects: list[Project] = []
        self._zoxide_entries: list[ZoxideEntry] = []
        self._items: list[Project | ZoxideEntry] = []
        self._index_map: dict[int, int] = {}  # option_index -> items_index
        self._statuses: dict[str, SessionStatus] = {}
        # Type icons cached by path, computed once when data loads so that
        # per-keystroke filtering never touches the filesystem.
        self._icon_cache: dict[str, str] = {}
        self._loaded = False

    def compose(self) -> ComposeResult:
        """Compose the modal."""
        with Vertical(id="search-container"):
            yield Static("[dim]󰍉 Quick Switch[/dim]", id="search-header")
            yield Input(placeholder="Type to search...", id="search-input")
            yield OptionList(id="search-results")

    def on_mount(self) -> None:
        """Kick off a background load and focus input on mount."""
        option_list = self.query_one("#search-results", OptionList)
        option_list.add_option(Option("[dim]Loading…[/dim]", disabled=True))
        self.query_one("#search-input", Input).focus()

        def _work() -> None:
            data = self._load_data()
            self.app.call_from_thread(self._apply_data, *data)

        self.run_worker(_work, thread=True, exclusive=True, group="search-load")

    def _load_data(
        self,
    ) -> tuple[list[Project], dict[str, SessionStatus], list[ZoxideEntry], dict[str, str]]:
        """Load projects, statuses and zoxide entries (runs in a worker thread)."""
        registry = get_registry()
        registry.reload()
        projects = list(registry.list_all())
        statuses = get_all_session_statuses()

        if is_zoxide_available():
            registered_paths = {p.path for p in projects}
            zoxide_entries = query_zoxide(limit=30, exclude_paths=registered_paths)
        else:
            zoxide_entries = []

        # Precompute all type icons here (filesystem I/O) so filtering is pure.
        icons: dict[str, str] = {}
        for p in projects:
            icons[p.path] = project_type_icon(detect_project_type(p.path).value)
        for e in zoxide_entries:
            icons[e.path] = project_type_icon(detect_project_type(e.path).value)

        return projects, statuses, zoxide_entries, icons

    def _apply_data(
        self,
        projects: list[Project],
        statuses: dict[str, SessionStatus],
        zoxide_entries: list[ZoxideEntry],
        icons: dict[str, str],
    ) -> None:
        """Store loaded data and render (main thread, no I/O)."""
        self._projects = projects
        self._statuses = statuses
        self._zoxide_entries = zoxide_entries
        self._icon_cache = icons
        self._loaded = True
        # Render with the current query (user may have typed while loading).
        try:
            query = self.query_one("#search-input", Input).value
        except Exception:
            query = ""
        self._render_items(query)

    def _render_items(self, query: str = "") -> None:
        """Render filtered items to the results list."""
        option_list = self.query_one("#search-results", OptionList)
        option_list.clear_options()
        self._items.clear()
        self._index_map.clear()

        query_lower = query.lower()
        option_idx = 0

        # Filter projects
        filtered_projects = [
            p
            for p in sorted(
                self._projects,
                key=lambda p: (p.last_opened or datetime.min,),
                reverse=True,
            )
            if not query or fuzzy_match(query_lower, p.name.lower())
        ]

        # Filter zoxide entries
        filtered_zoxide = [
            e for e in self._zoxide_entries if not query or fuzzy_match(query_lower, e.name.lower())
        ]

        # Add projects section
        if filtered_projects:
            option_list.add_option(Option("[bold cyan]󰉋 Projects[/bold cyan]", disabled=True))
            option_idx += 1

            for project in filtered_projects:
                status = self._statuses.get(project.name, SessionStatus.IDLE)
                indicator = status_indicator(status)
                type_icon = self._icon_cache.get(project.path) or project_type_icon("generic")

                label = (
                    f"  {indicator} {type_icon} {project.name}  [dim]{project.group.lower()}[/dim]"
                )
                option_list.add_option(Option(label))
                self._index_map[option_idx] = len(self._items)
                self._items.append(project)
                option_idx += 1

        # Add zoxide section
        if filtered_zoxide:
            if filtered_projects:
                option_list.add_option(
                    Option("[dim]╶───────────────────────────────────╴[/dim]", disabled=True)
                )
                option_idx += 1
            option_list.add_option(
                Option("[bold yellow]󰋚 Recent (not registered)[/bold yellow]", disabled=True)
            )
            option_idx += 1

            for entry in filtered_zoxide:
                type_icon = self._icon_cache.get(entry.path) or project_type_icon("generic")

                label = f"  [dim]○[/dim] [yellow]{type_icon}[/yellow] {entry.name}  [dim]{entry.path}[/dim]"
                option_list.add_option(Option(label))
                self._index_map[option_idx] = len(self._items)
                self._items.append(entry)
                option_idx += 1

        if not self._items:
            option_list.add_option(Option("[dim]No matches[/dim]", disabled=True))

        # Pre-select first selectable item
        self._select_first_item()

    def _select_first_item(self) -> None:
        """Pre-select the first selectable item."""
        option_list = self.query_one("#search-results", OptionList)
        # Find first selectable option (skip headers/separators)
        for idx in sorted(self._index_map.keys()):
            option_list.highlighted = idx
            break

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        # Ignore keystrokes until the background load has populated the lists.
        if not self._loaded:
            return
        self._render_items(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in search input."""
        self.action_select()

    def action_cancel(self) -> None:
        """Cancel and dismiss the modal."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the highlighted item."""
        option_list = self.query_one("#search-results", OptionList)
        idx = option_list.highlighted
        if idx is not None and idx in self._index_map:
            item_idx = self._index_map[idx]
            self.dismiss(self._items[item_idx])
        else:
            self.dismiss(None)

    def action_focus_results(self) -> None:
        """Focus the results list for navigation."""
        self.query_one("#search-results", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection via click or enter."""
        idx = event.option_index
        if idx in self._index_map:
            item_idx = self._index_map[idx]
            self.dismiss(self._items[item_idx])

    def on_key(self, event) -> None:
        """Handle key events for navigation."""
        if event.key in ("down", "up"):
            results = self.query_one("#search-results", OptionList)
            if not results.has_focus:
                results.focus()
                if event.key == "down" and results.highlighted is None:
                    results.highlighted = 0
