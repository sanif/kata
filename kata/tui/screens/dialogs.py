"""Generic modal dialogs shared across TUI screens.

These were previously defined inline in ``context_menu.py`` but are generic and
reused, so they live here to keep the context menu focused on its own actions.
"""

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from kata.services.registry import get_registry


class ConfirmDialog(ModalScreen[bool]):
    """Simple confirmation dialog."""

    CSS = """
    ConfirmDialog {
        align: center middle;
    }

    ConfirmDialog #dialog-container {
        width: 40;
        height: auto;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 1 2;
    }

    ConfirmDialog #dialog-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    ConfirmDialog #dialog-message {
        color: $text-muted;
        margin-bottom: 1;
    }

    ConfirmDialog #options {
        height: auto;
        background: $surface;
    }

    ConfirmDialog #options > .option-list--option-highlighted {
        background: $primary 20%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Yes", show=False),
        Binding("n", "cancel", "No", show=False),
    ]

    def __init__(
        self,
        title: str,
        message: str,
        confirm_label: str = "Confirm",
        *args,
        **kwargs,
    ) -> None:
        """Initialize confirmation dialog."""
        super().__init__(*args, **kwargs)
        self._title = title
        self._message = message
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Container(id="dialog-container"):
            yield Static(self._title, id="dialog-title")
            yield Static(self._message, id="dialog-message")
            yield OptionList(
                Option("Cancel", id="cancel"),
                Option(self._confirm_label, id="confirm"),
                id="options",
            )

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        self.dismiss(event.option.id == "confirm")

    def action_cancel(self) -> None:
        """Handle escape/n key."""
        self.dismiss(False)

    def action_confirm(self) -> None:
        """Handle y key."""
        self.dismiss(True)


class InputDialog(ModalScreen[str | None]):
    """Simple input dialog."""

    CSS = """
    InputDialog {
        align: center middle;
    }

    InputDialog #dialog-container {
        width: 60;
        height: auto;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 1 2;
    }

    InputDialog #dialog-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    InputDialog #dialog-message {
        margin-bottom: 1;
    }

    InputDialog #dialog-input {
        margin-bottom: 1;
    }

    InputDialog #dialog-buttons {
        width: 100%;
        height: auto;
        align: right middle;
    }

    InputDialog Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        title: str,
        message: str,
        default: str = "",
        *args,
        **kwargs,
    ) -> None:
        """Initialize input dialog."""
        super().__init__(*args, **kwargs)
        self._title = title
        self._message = message
        self._default = default

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Container(id="dialog-container"):
            yield Static(self._title, id="dialog-title")
            yield Static(self._message, id="dialog-message")
            yield Input(value=self._default, id="dialog-input")
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel", variant="default", id="cancel-btn")
                yield Button("OK", variant="primary", id="ok-btn")

    def on_mount(self) -> None:
        """Focus the input on mount."""
        self.query_one("#dialog-input", Input).focus()

    @on(Button.Pressed, "#cancel-btn")
    def on_cancel_pressed(self) -> None:
        """Handle cancel button."""
        self.dismiss(None)

    @on(Button.Pressed, "#ok-btn")
    def on_ok_pressed(self) -> None:
        """Handle OK button."""
        value = self.query_one("#dialog-input", Input).value
        self.dismiss(value)

    @on(Input.Submitted)
    def on_input_submitted(self) -> None:
        """Handle enter in input."""
        value = self.query_one("#dialog-input", Input).value
        self.dismiss(value)

    def action_cancel(self) -> None:
        """Handle escape key."""
        self.dismiss(None)


class GroupSelectorDialog(ModalScreen[str | None]):
    """Dialog for selecting a group."""

    CSS = """
    GroupSelectorDialog {
        align: center middle;
    }

    GroupSelectorDialog #dialog-container {
        width: 50;
        height: auto;
        max-height: 20;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 1 2;
    }

    GroupSelectorDialog #dialog-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    GroupSelectorDialog #group-list {
        height: auto;
        max-height: 10;
        margin-bottom: 1;
    }

    GroupSelectorDialog #new-group-container {
        height: auto;
        margin-bottom: 1;
    }

    GroupSelectorDialog #new-group-label {
        margin-bottom: 0;
    }

    GroupSelectorDialog #dialog-buttons {
        width: 100%;
        height: auto;
        align: right middle;
    }

    GroupSelectorDialog Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, current_group: str, *args, **kwargs) -> None:
        """Initialize group selector."""
        super().__init__(*args, **kwargs)
        self.current_group = current_group

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        registry = get_registry()
        groups = registry.get_groups()

        with Container(id="dialog-container"):
            yield Static("Move to Group", id="dialog-title")

            if groups:
                options = [
                    Option(f"{'● ' if g == self.current_group else '  '}{g}", id=g)
                    for g in sorted(groups)
                ]
                yield OptionList(*options, id="group-list")

            with Vertical(id="new-group-container"):
                yield Static("Or create new group:", id="new-group-label")
                yield Input(placeholder="New group name...", id="new-group-input")

            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel", variant="default", id="cancel-btn")

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle group selection from list."""
        if event.option.id:
            self.dismiss(event.option.id)

    @on(Input.Submitted, "#new-group-input")
    def on_new_group_submitted(self, event: Input.Submitted) -> None:
        """Handle new group input."""
        value = event.value.strip()
        if value:
            self.dismiss(value)

    @on(Button.Pressed, "#cancel-btn")
    def on_cancel_pressed(self) -> None:
        """Handle cancel button."""
        self.dismiss(None)

    def action_cancel(self) -> None:
        """Handle escape key."""
        self.dismiss(None)


class ShortcutSelectorDialog(ModalScreen[int | None]):
    """Dialog for selecting a shortcut number (1-9)."""

    CSS = """
    ShortcutSelectorDialog {
        align: center middle;
    }

    ShortcutSelectorDialog #dialog-container {
        width: 40;
        height: auto;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 1 2;
    }

    ShortcutSelectorDialog #dialog-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    ShortcutSelectorDialog #dialog-subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }

    ShortcutSelectorDialog #shortcut-list {
        height: auto;
        max-height: 12;
        background: $surface;
    }

    ShortcutSelectorDialog #shortcut-list > .option-list--option-highlighted {
        background: $primary 20%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("1", "select(1)", "1", show=False),
        Binding("2", "select(2)", "2", show=False),
        Binding("3", "select(3)", "3", show=False),
        Binding("4", "select(4)", "4", show=False),
        Binding("5", "select(5)", "5", show=False),
        Binding("6", "select(6)", "6", show=False),
        Binding("7", "select(7)", "7", show=False),
        Binding("8", "select(8)", "8", show=False),
        Binding("9", "select(9)", "9", show=False),
        Binding("0", "clear_shortcut", "Clear", show=False),
    ]

    def __init__(
        self,
        current_shortcut: int | None,
        project_name: str,
        *args,
        **kwargs,
    ) -> None:
        """Initialize shortcut selector."""
        super().__init__(*args, **kwargs)
        self.current_shortcut = current_shortcut
        self.project_name = project_name

    def compose(self) -> ComposeResult:
        """Compose the dialog."""
        with Container(id="dialog-container"):
            yield Static("Set Shortcut", id="dialog-title")
            yield Static("[dim]Press 1-9 or select below[/dim]", id="dialog-subtitle")

            options = []
            for i in range(1, 10):
                marker = "● " if i == self.current_shortcut else "  "
                options.append(Option(f"{marker}({i})", id=str(i)))

            # Add clear option
            options.append(Option("  (0) Clear shortcut", id="clear"))

            yield OptionList(*options, id="shortcut-list")

    def on_mount(self) -> None:
        """Highlight current shortcut."""
        if self.current_shortcut:
            try:
                option_list = self.query_one("#shortcut-list", OptionList)
                option_list.highlighted = self.current_shortcut - 1
            except Exception:
                pass

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        if event.option.id == "clear":
            self.dismiss(-1)
        else:
            try:
                self.dismiss(int(event.option.id))
            except (ValueError, TypeError):
                self.dismiss(None)

    def action_cancel(self) -> None:
        """Handle escape key."""
        self.dismiss(None)

    def action_clear_shortcut(self) -> None:
        """Clear shortcut (0 key)."""
        self.dismiss(-1)

    def action_select(self, number: int) -> None:
        """Select a shortcut number (1-9 keys)."""
        self.dismiss(number)


class ColorSelectorDialog(ModalScreen[str | None]):
    """Dialog for selecting a project color from presets."""

    CSS = """
    ColorSelectorDialog {
        align: center middle;
    }

    ColorSelectorDialog #dialog-container {
        width: 40;
        height: auto;
        max-height: 22;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 1 2;
    }

    ColorSelectorDialog #dialog-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    ColorSelectorDialog #color-list {
        height: auto;
        max-height: 16;
        background: $surface;
    }

    ColorSelectorDialog #color-list > .option-list--option-highlighted {
        background: $primary 20%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        current_color: str | None,
        project_name: str,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.current_color = current_color
        self.project_name = project_name

    def compose(self) -> ComposeResult:
        from kata.utils.colors import COLOR_PRESETS, resolve_color

        current_hex = resolve_color(self.current_color)

        with Container(id="dialog-container"):
            yield Static("Set Color", id="dialog-title")

            options = []
            highlight_index = None
            for i, (name, hex_val) in enumerate(COLOR_PRESETS.items()):
                marker = "● " if hex_val == current_hex else "  "
                options.append(Option(f"{marker}[{hex_val}]██[/{hex_val}]  {name}", id=name))
                if hex_val == current_hex:
                    highlight_index = i

            options.append(Option("  ○  Clear color", id="clear"))

            yield OptionList(*options, id="color-list")

            self._highlight_index = highlight_index

    def on_mount(self) -> None:
        if self._highlight_index is not None:
            try:
                option_list = self.query_one("#color-list", OptionList)
                option_list.highlighted = self._highlight_index
            except Exception:
                pass

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "clear":
            self.dismiss("clear")
        elif event.option.id:
            self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)
