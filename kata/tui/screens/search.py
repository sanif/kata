"""Search modal screen for quick project/directory switching."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from kata.core.models import Project, SessionStatus
from kata.services.registry import get_registry
from kata.services.sessions import get_all_session_statuses
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


class SearchModal(ModalScreen[Project | ZoxideEntry | None]):
    """Modal search screen for quick switching."""

    DEFAULT_CSS = """
    SearchModal {
        align: center middle;
    }

    SearchModal #search-container {
        width: 70;
        height: 20;
        background: $surface;
        border: solid $primary;
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
        background: $primary 30%;
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

    def compose(self) -> ComposeResult:
        """Compose the modal."""
        with Vertical(id="search-container"):
            yield Static("[dim]󰍉 search[/dim]", id="search-header")
            yield Input(placeholder="Type to search...", id="search-input")
            yield OptionList(id="search-results")

    def on_mount(self) -> None:
        """Load data and focus input on mount."""
        self._load_data()
        self._render_items()
        self.query_one("#search-input", Input).focus()

    def _load_data(self) -> None:
        """Load projects and zoxide entries."""
        registry = get_registry()
        self._projects = list(registry.list_all())
        self._statuses = get_all_session_statuses()

        if is_zoxide_available():
            registered_paths = {p.path for p in self._projects}
            self._zoxide_entries = query_zoxide(limit=30, exclude_paths=registered_paths)
        else:
            self._zoxide_entries = []

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
            p for p in sorted(self._projects, key=lambda p: p.name)
            if not query or self._fuzzy_match(query_lower, p.name.lower())
        ]

        # Filter zoxide entries
        filtered_zoxide = [
            e for e in self._zoxide_entries
            if not query or self._fuzzy_match(query_lower, e.name.lower())
        ]

        # Add projects section
        if filtered_projects:
            option_list.add_option(Option("[bold cyan]󰉋 Projects[/bold cyan]", disabled=True))
            option_idx += 1

            for project in filtered_projects:
                status = self._statuses.get(project.name, SessionStatus.IDLE)
                indicator = self._get_status_indicator(status)
                project_type = detect_project_type(project.path)
                type_icon = PROJECT_TYPE_ICONS.get(project_type.value, PROJECT_TYPE_ICONS["generic"])

                label = f"  {indicator} {type_icon} {project.name}  [dim]{project.group.lower()}[/dim]"
                option_list.add_option(Option(label))
                self._index_map[option_idx] = len(self._items)
                self._items.append(project)
                option_idx += 1

        # Add zoxide section
        if filtered_zoxide:
            if filtered_projects:
                option_list.add_option(Option("[dim]─────────────────────────────────────────[/dim]", disabled=True))
                option_idx += 1
            option_list.add_option(Option("[bold yellow]󰋚 Recent (not registered)[/bold yellow]", disabled=True))
            option_idx += 1

            for entry in filtered_zoxide:
                project_type = detect_project_type(entry.path)
                type_icon = PROJECT_TYPE_ICONS.get(project_type.value, PROJECT_TYPE_ICONS["generic"])

                label = f"  [dim]◇[/dim] [yellow]{type_icon}[/yellow] {entry.name}  [dim]{entry.path}[/dim]"
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

    def _get_status_indicator(self, status: SessionStatus) -> str:
        """Get the status indicator for a session status."""
        indicators = {
            SessionStatus.ACTIVE: "[green]◆[/green]",
            SessionStatus.DETACHED: "[yellow]◆[/yellow]",
            SessionStatus.IDLE: "[dim]◇[/dim]",
        }
        return indicators.get(status, "[dim]◇[/dim]")

    def _fuzzy_match(self, query: str, target: str) -> bool:
        """Check if query fuzzy matches target."""
        if not query:
            return True
        query_idx = 0
        for char in target:
            if query_idx < len(query) and char == query[query_idx]:
                query_idx += 1
        return query_idx == len(query)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
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
