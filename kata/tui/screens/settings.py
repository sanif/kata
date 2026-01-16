"""Settings screen for TUI."""

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static, Switch
from textual.widgets.option_list import Option

from kata.core.settings import (
    AVAILABLE_THEMES,
    Settings,
    get_settings,
    update_settings,
)


class SettingsScreen(ModalScreen[None]):
    """Modal screen for application settings."""

    CSS = """
    SettingsScreen {
        align: center middle;
    }

    SettingsScreen #settings-container {
        width: 60;
        height: auto;
        max-height: 35;
        background: $surface;
        border: solid $surface-lighten-1;
        padding: 1 2;
        overflow-y: auto;
    }

    SettingsScreen #settings-title {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
        text-align: center;
    }

    SettingsScreen .setting-row {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    SettingsScreen .setting-label {
        width: 20;
        height: 3;
        content-align: left middle;
    }

    SettingsScreen .setting-control {
        width: 1fr;
        height: 3;
    }

    SettingsScreen .setting-description {
        color: $text-muted;
        margin-left: 20;
        margin-bottom: 1;
    }

    SettingsScreen #theme-list {
        height: auto;
        max-height: 8;
        margin-left: 2;
        margin-bottom: 1;
        background: $surface;
    }

    SettingsScreen #interval-input {
        width: 10;
    }

    SettingsScreen #group-input {
        width: 30;
    }

    SettingsScreen #settings-footer {
        width: 100%;
        height: auto;
        margin-top: 1;
        align: right middle;
    }

    SettingsScreen .restart-notice {
        color: $warning;
        text-style: italic;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    class SettingsChanged(Message):
        """Emitted when settings change."""

        def __init__(self, settings: Settings) -> None:
            super().__init__()
            self.settings = settings

    # Theme display names
    THEME_NAMES = {
        "kata-dark": "Kata Dark",
        "kata-light": "Kata Light",
        "kata-ocean": "Kata Ocean",
        "kata-warm": "Kata Warm",
    }

    def __init__(self, *args, **kwargs) -> None:
        """Initialize settings screen."""
        super().__init__(*args, **kwargs)
        self._settings = get_settings()
        self._theme_changed = False

    def _format_theme_name(self, theme_id: str) -> str:
        """Format theme ID to display name."""
        return self.THEME_NAMES.get(theme_id, theme_id.replace("-", " ").title())

    def compose(self) -> ComposeResult:
        """Compose the settings screen."""
        with Container(id="settings-container"):
            yield Static("Settings", id="settings-title")

            # Loop Mode Toggle
            with Horizontal(classes="setting-row"):
                yield Static("Loop Mode:", classes="setting-label")
                yield Switch(
                    value=self._settings.loop_enabled,
                    id="loop-switch",
                    classes="setting-control",
                )
            yield Static(
                "Auto-launch dashboard after session exits",
                classes="setting-description",
            )

            # Default Group Input
            with Horizontal(classes="setting-row"):
                yield Static("Default Group:", classes="setting-label")
                yield Input(
                    value=self._settings.default_group,
                    placeholder="Group name...",
                    id="group-input",
                    classes="setting-control",
                )
            yield Static(
                "Group for new projects without explicit group",
                classes="setting-description",
            )

            # Refresh Interval Input
            with Horizontal(classes="setting-row"):
                yield Static("Refresh (sec):", classes="setting-label")
                yield Input(
                    value=str(self._settings.refresh_interval),
                    placeholder="1-60",
                    id="interval-input",
                    classes="setting-control",
                )
            yield Static(
                "Status refresh interval (1-60 seconds)",
                classes="setting-description",
            )

            # Theme Selector
            yield Static("Theme:", classes="setting-label")
            theme_options = [
                Option(
                    f"{'● ' if t == self._settings.theme else '  '}{self._format_theme_name(t)}",
                    id=t,
                )
                for t in AVAILABLE_THEMES
            ]
            yield OptionList(*theme_options, id="theme-list")
            yield Static(
                "Select a theme for the interface",
                classes="setting-description",
                id="theme-notice",
            )

            # Footer with close button
            with Horizontal(id="settings-footer"):
                yield Button("Close", variant="primary", id="close-btn")

    def on_mount(self) -> None:
        """Focus first input on mount."""
        pass  # Let user navigate naturally

    @on(Switch.Changed, "#loop-switch")
    def on_loop_changed(self, event: Switch.Changed) -> None:
        """Handle loop mode toggle."""
        update_settings(loop_enabled=event.value)
        self._settings = get_settings()
        self.post_message(self.SettingsChanged(self._settings))

    @on(Input.Changed, "#group-input")
    def on_group_changed(self, event: Input.Changed) -> None:
        """Handle default group change."""
        value = event.value.strip()
        if value:
            update_settings(default_group=value)
            self._settings = get_settings()
            self.post_message(self.SettingsChanged(self._settings))

    @on(Input.Changed, "#interval-input")
    def on_interval_changed(self, event: Input.Changed) -> None:
        """Handle refresh interval change."""
        try:
            value = int(event.value.strip())
            # Clamp to valid range
            value = max(1, min(60, value))
            update_settings(refresh_interval=value)
            self._settings = get_settings()
            self.post_message(self.SettingsChanged(self._settings))
        except ValueError:
            pass  # Ignore invalid input while typing

    @on(OptionList.OptionSelected, "#theme-list")
    def on_theme_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle theme selection."""
        if event.option.id and event.option.id != self._settings.theme:
            update_settings(theme=event.option.id)
            self._settings = get_settings()
            self._theme_changed = True

            # Apply theme immediately
            self.app.theme = event.option.id

            # Update the list to show selection
            try:
                theme_list = self.query_one("#theme-list", OptionList)
                theme_list.clear_options()
                for t in AVAILABLE_THEMES:
                    prefix = "● " if t == self._settings.theme else "  "
                    theme_list.add_option(Option(f"{prefix}{self._format_theme_name(t)}", id=t))
            except Exception:
                pass

            self.app.notify(
                f"Theme: {self._format_theme_name(event.option.id)}",
                title="Theme Applied",
            )
            self.post_message(self.SettingsChanged(self._settings))

    @on(Button.Pressed, "#close-btn")
    def on_close_pressed(self) -> None:
        """Handle close button."""
        self.dismiss(None)

    def action_close(self) -> None:
        """Handle escape key."""
        self.dismiss(None)
