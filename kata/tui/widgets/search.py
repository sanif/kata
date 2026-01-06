"""Search input widget for filtering projects."""

from textual import on
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input


class SearchInput(Widget):
    """Search input widget with fuzzy filtering support."""

    DEFAULT_CSS = """
    SearchInput {
        width: 100%;
        height: 3;
        padding: 0 1;
        background: $background;
    }

    SearchInput > Input {
        width: 100%;
        background: $surface;
        border: none;
        color: $text;
    }

    SearchInput > Input:focus {
        border: none;
    }

    SearchInput > Input > .input--placeholder {
        color: $text-muted;
    }

    SearchInput.-hidden {
        display: none;
    }
    """

    class SearchChanged(Message):
        """Message sent when search query changes."""

        def __init__(self, query: str) -> None:
            super().__init__()
            self.query = query

    class SearchCancelled(Message):
        """Message sent when search is cancelled (Escape)."""

        pass

    class SearchSubmitted(Message):
        """Message sent when search is submitted (Enter)."""

        def __init__(self, query: str) -> None:
            super().__init__()
            self.query = query

    query: reactive[str] = reactive("", init=False)
    visible: reactive[bool] = reactive(False)

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the search input."""
        super().__init__(name=name, id=id, classes=classes)
        self.query = ""

    def compose(self):
        """Compose the widget."""
        yield Input(placeholder="Search projects...", id="search-input")

    def on_mount(self) -> None:
        """Hide by default."""
        if not self.visible:
            self.add_class("-hidden")

    def watch_visible(self, visible: bool) -> None:
        """React to visibility changes."""
        if visible:
            self.remove_class("-hidden")
            self.query_one("#search-input", Input).focus()
        else:
            self.add_class("-hidden")
            self.query_one("#search-input", Input).value = ""
            self.query = ""

    def show(self) -> None:
        """Show the search input and focus it."""
        self.visible = True

    def hide(self) -> None:
        """Hide the search input and clear it."""
        self.visible = False
        self.post_message(self.SearchCancelled())

    def clear(self) -> None:
        """Clear the search query."""
        self.query_one("#search-input", Input).value = ""
        self.query = ""
        self.post_message(self.SearchChanged(""))

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        self.query = event.value
        self.post_message(self.SearchChanged(event.value))

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        self.post_message(self.SearchSubmitted(self.query))

    def key_escape(self) -> None:
        """Handle Escape key to cancel search."""
        self.hide()
