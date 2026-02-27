"""Settings screen for TUI."""

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static, Switch
from textual.widgets.option_list import Option

from kata.core.settings import (
    AVAILABLE_THEMES,
    Settings,
    get_settings,
    update_settings,
)
from kata.services.notifications.sounds import AVAILABLE_SOUND_PACKS
from kata.services.registry import get_registry


class SettingsScreen(ModalScreen[None]):
    """Modal screen for application settings."""

    CSS = """
    SettingsScreen {
        align: center middle;
    }

    SettingsScreen #settings-container {
        width: 66;
        height: auto;
        max-height: 38;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 1 2;
    }

    SettingsScreen #settings-title {
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
        text-align: center;
        width: 100%;
    }

    SettingsScreen #settings-scroll {
        width: 100%;
        height: auto;
        max-height: 32;
    }

    SettingsScreen .section-divider {
        width: 100%;
        height: 1;
        color: $text-muted;
        margin-top: 1;
    }

    SettingsScreen .setting-group {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 0;
    }

    SettingsScreen .setting-name {
        width: 100%;
        height: 1;
        color: $text;
    }

    SettingsScreen .setting-hint {
        color: $text-muted;
    }

    SettingsScreen .toggle-row {
        width: 100%;
        height: 3;
        align: left middle;
    }

    SettingsScreen .toggle-label {
        width: 1fr;
        height: auto;
        content-align: left middle;
    }

    SettingsScreen Switch {
        margin-bottom: 0;
    }

    SettingsScreen Input {
        width: 100%;
        max-width: 40;
    }

    SettingsScreen #theme-list {
        width: 100%;
        height: auto;
        max-height: 6;
        background: $surface;
        border: tall $surface-lighten-1;
    }

    SettingsScreen #theme-list:focus {
        border: tall $primary;
    }

    SettingsScreen #sound-pack-list {
        width: 100%;
        height: auto;
        max-height: 5;
        background: $surface;
        border: tall $surface-lighten-1;
    }

    SettingsScreen #sound-pack-list:focus {
        border: tall $primary;
    }

    SettingsScreen #project-notif-list {
        width: 100%;
        height: auto;
        max-height: 5;
        background: $surface;
        border: tall $surface-lighten-1;
    }

    SettingsScreen #project-notif-list:focus {
        border: tall $primary;
    }

    SettingsScreen #settings-footer {
        width: 100%;
        height: 1;
        margin-top: 1;
        content-align: center middle;
        color: $text-muted;
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
        "kata-glass": "Kata Glass",
        "kata-glass-light": "Kata Glass Light",
        "kata-rose": "Kata Rose",
        "kata-nord": "Kata Nord",
        "kata-mono": "Kata Mono",
        "kata-ember": "Kata Ember",
    }

    def __init__(self, *args, **kwargs) -> None:
        """Initialize settings screen."""
        super().__init__(*args, **kwargs)
        self._settings = get_settings()
        self._theme_changed = False
        self._projects: list[str] = []

    def _format_theme_name(self, theme_id: str) -> str:
        """Format theme ID to display name."""
        return self.THEME_NAMES.get(theme_id, theme_id.replace("-", " ").title())

    def _make_divider(self, label: str) -> str:
        """Create a thin section divider: ── Label ──."""
        pad = 60 - len(label) - 4  # account for ── and ── with spaces
        left = pad // 2
        right = pad - left
        return f"[dim]{'─' * left} {label} {'─' * right}[/dim]"

    def compose(self) -> ComposeResult:
        """Compose the settings screen."""
        # Load project names for per-project list
        registry = get_registry()
        self._projects = sorted([p.name for p in registry.list_all()])

        with Vertical(id="settings-container"):
            yield Static("󰒓 Settings", id="settings-title")

            with VerticalScroll(id="settings-scroll"):
                # -- General --
                yield Static(self._make_divider("General"), classes="section-divider")

                with Vertical(classes="setting-group"):
                    with Horizontal(classes="toggle-row"):
                        with Vertical(classes="toggle-label"):
                            yield Static("[bold]Loop Mode[/bold]")
                            yield Static(
                                "[dim]Auto-launch dashboard after session exits[/dim]",
                                classes="setting-hint",
                            )
                        yield Switch(value=self._settings.loop_enabled, id="loop-switch")

                with Vertical(classes="setting-group"):
                    yield Static(
                        f"[bold]Default Group[/bold]  [dim]{self._settings.default_group or '(none)'}[/dim]",
                        classes="setting-name",
                    )
                    yield Input(
                        value=self._settings.default_group,
                        placeholder="Group name...",
                        id="group-input",
                    )

                with Vertical(classes="setting-group"):
                    yield Static(
                        f"[bold]Refresh Interval[/bold]  [dim]{self._settings.refresh_interval}s (1-60)[/dim]",
                        classes="setting-name",
                    )
                    yield Input(
                        value=str(self._settings.refresh_interval),
                        placeholder="1-60",
                        id="interval-input",
                    )

                # -- Notifications --
                yield Static(self._make_divider("Notifications"), classes="section-divider")

                with Vertical(classes="setting-group"):
                    with Horizontal(classes="toggle-row"):
                        with Vertical(classes="toggle-label"):
                            yield Static("[bold]Notifications[/bold]")
                            yield Static(
                                "[dim]Desktop and sound notifications[/dim]",
                                classes="setting-hint",
                            )
                        yield Switch(
                            value=self._settings.notifications_enabled,
                            id="notif-switch",
                        )

                with Vertical(classes="setting-group"):
                    yield Static("[bold]Sound Pack[/bold]", classes="setting-name")
                    pack_options = [
                        Option(
                            f"{'● ' if p == self._settings.notifications_sound_pack else '  '}{name}",
                            id=p,
                        )
                        for p, name in AVAILABLE_SOUND_PACKS.items()
                    ]
                    yield OptionList(*pack_options, id="sound-pack-list")

                with Vertical(classes="setting-group"):
                    yield Static(
                        "[bold]Per Project[/bold]  [dim]Enter to toggle[/dim]",
                        classes="setting-name",
                    )
                    disabled = set(self._settings.notifications_disabled_projects)
                    options = [
                        Option(
                            f"{'[green]●[/green]' if name not in disabled else '[dim]○[/dim]'}  {name}",
                            id=name,
                        )
                        for name in self._projects
                    ]
                    yield OptionList(*options, id="project-notif-list")

                # -- Appearance --
                yield Static(self._make_divider("Appearance"), classes="section-divider")

                with Vertical(classes="setting-group"):
                    yield Static("[bold]Theme[/bold]", classes="setting-name")
                    theme_options = [
                        Option(
                            f"{'● ' if t == self._settings.theme else '  '}{self._format_theme_name(t)}",
                            id=t,
                        )
                        for t in AVAILABLE_THEMES
                    ]
                    yield OptionList(*theme_options, id="theme-list")

            yield Static("[dim]esc to close[/dim]", id="settings-footer")

    def on_mount(self) -> None:
        """Focus first interactive widget on mount."""
        try:
            self.query_one("#loop-switch", Switch).focus()
        except Exception:
            pass

    def on_descendant_focus(self, event) -> None:
        """Auto-scroll to keep focused widget visible."""
        try:
            event.widget.scroll_visible()
        except Exception:
            pass

    def _refresh_project_notif_list(self) -> None:
        """Refresh the per-project notification list to reflect current state."""
        try:
            option_list = self.query_one("#project-notif-list", OptionList)
            disabled = set(self._settings.notifications_disabled_projects)
            option_list.clear_options()
            for name in self._projects:
                indicator = "[green]●[/green]" if name not in disabled else "[dim]○[/dim]"
                option_list.add_option(Option(f"{indicator}  {name}", id=name))
        except Exception:
            pass

    @on(Switch.Changed, "#loop-switch")
    def on_loop_changed(self, event: Switch.Changed) -> None:
        """Handle loop mode toggle."""
        update_settings(loop_enabled=event.value)
        self._settings = get_settings()
        self.post_message(self.SettingsChanged(self._settings))

    @on(Switch.Changed, "#notif-switch")
    def on_notif_changed(self, event: Switch.Changed) -> None:
        """Handle global notifications toggle."""
        update_settings(notifications_enabled=event.value)
        self._settings = get_settings()
        self.post_message(self.SettingsChanged(self._settings))

    @on(OptionList.OptionSelected, "#sound-pack-list")
    def on_sound_pack_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle sound pack selection."""
        if event.option.id and event.option.id != self._settings.notifications_sound_pack:
            update_settings(notifications_sound_pack=event.option.id)
            self._settings = get_settings()

            # Update the list to show selection
            try:
                pack_list = self.query_one("#sound-pack-list", OptionList)
                pack_list.clear_options()
                for p, name in AVAILABLE_SOUND_PACKS.items():
                    prefix = "● " if p == self._settings.notifications_sound_pack else "  "
                    pack_list.add_option(Option(f"{prefix}{name}", id=p))
            except Exception:
                pass

            pack_name = AVAILABLE_SOUND_PACKS.get(event.option.id, event.option.id)
            self.app.notify(f"Sound pack: {pack_name}", title="Sounds")
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
            value = max(1, min(60, value))
            update_settings(refresh_interval=value)
            self._settings = get_settings()
            self.post_message(self.SettingsChanged(self._settings))
        except ValueError:
            pass

    @on(OptionList.OptionSelected, "#project-notif-list")
    def on_project_notif_toggled(self, event: OptionList.OptionSelected) -> None:
        """Toggle per-project notification on Enter."""
        project_name = event.option.id
        if not project_name:
            return

        disabled = list(self._settings.notifications_disabled_projects)
        if project_name in disabled:
            disabled.remove(project_name)
        else:
            disabled.append(project_name)

        update_settings(notifications_disabled_projects=disabled)
        self._settings = get_settings()
        self._refresh_project_notif_list()
        self.post_message(self.SettingsChanged(self._settings))

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

    def action_close(self) -> None:
        """Handle escape key."""
        self.dismiss(None)
