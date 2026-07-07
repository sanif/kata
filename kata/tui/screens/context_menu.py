"""Context Menu screen for project actions."""

import platform
import shlex
import subprocess
from enum import Enum, auto

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from kata.core.config import get_project_config_path
from kata.core.constants import SUBPROCESS_TIMEOUT
from kata.core.models import Project
from kata.core.settings import get_settings, update_settings
from kata.services.registry import get_registry
from kata.services.sessions import (
    SessionError,
    SessionNotFoundError,
    kill_session,
    rename_session,
    save_current_session_layout,
    session_exists,
    session_name_for,
)
from kata.services.tmux_style import apply_project_color, clear_project_color
from kata.tui.screens.dialogs import (
    ColorSelectorDialog,
    ConfirmDialog,
    GroupSelectorDialog,
    InputDialog,
    ShortcutSelectorDialog,
)
from kata.utils.paths import sanitize_session_name


class MenuAction(Enum):
    """Available context menu actions."""

    KILL = auto()
    DELETE = auto()
    RENAME = auto()
    MOVE_GROUP = auto()
    OPEN_TERMINAL = auto()
    BROWSE_FILES = auto()
    VIEW_CHANGES = auto()
    OPEN_WORKSPACE = auto()
    SAVE_LAYOUT = auto()
    SET_SHORTCUT = auto()
    TOGGLE_NOTIFICATIONS = auto()
    SET_COLOR = auto()


# Dispatch tables mapping actions/option IDs to method names
_ACTION_METHODS: dict[MenuAction, str] = {
    MenuAction.KILL: "action_kill_session",
    MenuAction.DELETE: "action_delete_project",
    MenuAction.RENAME: "action_rename_project",
    MenuAction.MOVE_GROUP: "action_move_group",
    MenuAction.OPEN_TERMINAL: "action_open_terminal",
    MenuAction.BROWSE_FILES: "action_browse_files",
    MenuAction.VIEW_CHANGES: "action_view_changes",
    MenuAction.OPEN_WORKSPACE: "action_open_workspace",
    MenuAction.SAVE_LAYOUT: "action_save_layout",
    MenuAction.SET_SHORTCUT: "action_set_shortcut",
    MenuAction.TOGGLE_NOTIFICATIONS: "action_toggle_notifications",
    MenuAction.SET_COLOR: "action_set_color",
}

_OPTION_METHODS: dict[str, str] = {
    "kill": "action_kill_session",
    "delete": "action_delete_project",
    "rename": "action_rename_project",
    "move_group": "action_move_group",
    "open_terminal": "action_open_terminal",
    "browse_files": "action_browse_files",
    "view_changes": "action_view_changes",
    "open_workspace": "action_open_workspace",
    "save_layout": "action_save_layout",
    "set_shortcut": "action_set_shortcut",
    "toggle_notifications": "action_toggle_notifications",
    "set_color": "action_set_color",
}


class ContextMenuScreen(ModalScreen[str | None]):
    """Modal context menu for project actions."""

    CSS = """
    ContextMenuScreen {
        align: center middle;
    }

    ContextMenuScreen #menu-container {
        width: 40;
        height: auto;
        max-height: 20;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 1 2;
    }

    ContextMenuScreen #menu-title {
        text-style: bold;
        color: $text;
        margin-bottom: 0;
    }

    ContextMenuScreen #menu-subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }

    ContextMenuScreen #menu-list {
        height: auto;
        max-height: 10;
        background: $surface;
        scrollbar-size: 1 1;
    }

    ContextMenuScreen #menu-list > .option-list--option {
        padding: 0 1;
    }

    ContextMenuScreen #menu-list > .option-list--option-highlighted {
        background: $primary 20%;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("k", "kill_session", "Kill", show=False),
        Binding("d", "delete_project", "Delete", show=False),
        Binding("r", "rename_project", "Rename", show=False),
        Binding("g", "move_group", "Move to Group", show=False),
        Binding("t", "open_terminal", "Open Terminal", show=False),
        Binding("f", "browse_files", "Browse Files", show=False),
        Binding("v", "view_changes", "View Changes", show=False),
        Binding("w", "open_workspace", "Open Workspace", show=False),
        Binding("l", "save_layout", "Save Layout", show=False),
        Binding("s", "set_shortcut", "Set Shortcut", show=False),
        Binding("n", "toggle_notifications", "Toggle Notifications", show=False),
        Binding("c", "set_color", "Set Color", show=False),
    ]

    # Allow pre-selecting an action when opening
    preselected_action: MenuAction | None = None

    def __init__(
        self,
        project: Project,
        preselected: MenuAction | None = None,
        *args,
        **kwargs,
    ) -> None:
        """Initialize context menu.

        Args:
            project: The project to perform actions on
            preselected: Optional action to pre-select and execute
        """
        super().__init__(*args, **kwargs)
        self.project = project
        self.preselected_action = preselected

    def compose(self) -> ComposeResult:
        """Compose the context menu."""
        with Container(id="menu-container"):
            yield Static("󰍜 Actions", id="menu-title")
            yield Static(f"[dim]{self.project.name}[/dim]", id="menu-subtitle")

            # Show current shortcut if set
            shortcut_label = "[dim]s[/dim]  󰖟 Set Shortcut"
            if self.project.shortcut:
                shortcut_label = (
                    f"[dim]s[/dim]  󰖟 Set Shortcut [dim]({self.project.shortcut})[/dim]"
                )

            # Notification status for this project
            settings = get_settings()
            notif_disabled = self.project.name in settings.notifications_disabled_projects
            notif_indicator = "[dim]○[/dim]" if notif_disabled else "[green]●[/green]"
            notif_label = f"[dim]n[/dim]  {notif_indicator} Notifications"

            # Color indicator
            from kata.utils.colors import resolve_color

            project_color = resolve_color(getattr(self.project, "color", None))
            if project_color:
                color_label = f"[dim]c[/dim]  [{project_color}]██[/{project_color}] Set Color"
            else:
                color_label = "[dim]c[/dim]  󰏘 Set Color"

            options = [
                Option("[dim]k[/dim]  󰅖 Kill Session", id="kill"),
                Option("[dim]d[/dim]  󰆴 Delete Project", id="delete"),
                Option("[dim]r[/dim]  󰑕 Rename", id="rename"),
                Option("[dim]g[/dim]  󰉋 Move to Group", id="move_group"),
                Option("[dim]t[/dim]  󰆍 Open in Terminal", id="open_terminal"),
                Option("[dim]f[/dim]  󰉋 Browse Files", id="browse_files"),
                Option("[dim]v[/dim]  󰊢 View Changes", id="view_changes"),
                Option("[dim]w[/dim]  󰆍 Open Workspace", id="open_workspace"),
                Option("[dim]l[/dim]  󰈙 Save Layout", id="save_layout"),
                Option(shortcut_label, id="set_shortcut"),
                Option(notif_label, id="toggle_notifications"),
                Option(color_label, id="set_color"),
            ]
            yield OptionList(*options, id="menu-list")

    def on_mount(self) -> None:
        """Handle mount - execute preselected action if any."""
        if self.preselected_action:
            # Highlight the preselected option in the list
            actions = list(_ACTION_METHODS.keys())
            index = (
                actions.index(self.preselected_action) if self.preselected_action in actions else 0
            )
            try:
                menu_list = self.query_one("#menu-list", OptionList)
                menu_list.highlighted = index
            except Exception:
                pass
            # Execute the preselected action immediately
            self.set_timer(0.1, self._execute_preselected)

    def _execute_preselected(self) -> None:
        """Execute the preselected action."""
        method_name = _ACTION_METHODS.get(self.preselected_action)
        if method_name:
            getattr(self, method_name)()

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        method_name = _OPTION_METHODS.get(event.option.id)
        if method_name:
            getattr(self, method_name)()

    def action_cancel(self) -> None:
        """Cancel and close the menu."""
        self.dismiss(None)

    def action_kill_session(self) -> None:
        """Kill the project's tmux session."""
        self.app.push_screen(
            ConfirmDialog(
                title="Kill Session",
                message=f"Kill tmux session for '{self.project.name}'?",
                confirm_label="Kill",
            ),
            self._on_kill_confirm,
        )

    def _on_kill_confirm(self, confirmed: bool) -> None:
        """Handle kill confirmation."""
        if not confirmed:
            return

        session_name = session_name_for(self.project)
        if not session_exists(session_name):
            self.app.notify("No active session to kill", severity="warning")
            self.dismiss(None)
            return

        try:
            kill_session(session_name)
            self.app.notify(f"Killed session: {self.project.name}", title="Success")
            self.dismiss("killed")
        except SessionNotFoundError:
            self.app.notify("Session not found", severity="warning")
            self.dismiss(None)
        except Exception as e:
            self.app.notify(f"Failed to kill session: {e}", severity="error")
            self.dismiss(None)

    def action_delete_project(self) -> None:
        """Delete the project from registry."""
        self.app.push_screen(
            ConfirmDialog(
                title="Delete Project",
                message=f"Delete '{self.project.name}' from registry?\n(Files will NOT be deleted)",
                confirm_label="Delete",
            ),
            self._on_delete_confirm,
        )

    def _on_delete_confirm(self, confirmed: bool) -> None:
        """Handle delete confirmation."""
        if not confirmed:
            return

        try:
            registry = get_registry()
            registry.remove(self.project.name)
            self.app.notify(f"Deleted project: {self.project.name}", title="Success")
            self.dismiss("deleted")
        except Exception as e:
            self.app.notify(f"Failed to delete project: {e}", severity="error")
            self.dismiss(None)

    def action_rename_project(self) -> None:
        """Rename the project."""
        self.app.push_screen(
            InputDialog(
                title="Rename Project",
                message="Enter new name:",
                default=self.project.name,
            ),
            self._on_rename_input,
        )

    def _on_rename_input(self, new_name: str | None) -> None:
        """Handle rename input."""
        if not new_name or new_name == self.project.name:
            return

        # Validate name
        new_name = new_name.strip()
        if not new_name:
            self.app.notify("Name cannot be empty", severity="error")
            return

        # Check for duplicates
        registry = get_registry()
        if new_name in registry:
            self.app.notify(f"Project '{new_name}' already exists", severity="error")
            return

        old_name = self.project.name
        # Resolve the live session name BEFORE mutating anything (honours an
        # edited session_name: in .kata.yaml).
        old_session = session_name_for(self.project)
        new_session = sanitize_session_name(new_name)

        # 1. Registry rename (remove old, add under the new, verified-unique name).
        try:
            registry.remove(old_name)
            self.project.name = new_name
            registry.add(self.project)
        except Exception as e:
            # Best-effort restore of the original registry entry.
            try:
                self.project.name = old_name
                if old_name not in registry:
                    registry.add(self.project)
            except Exception:
                pass
            self.app.notify(f"Failed to rename: {e}", severity="error")
            self.dismiss(None)
            return

        # 2. Rewrite session_name: in the project's .kata.yaml and rename any
        #    running session so the next launch resolves to the same session.
        try:
            self._rewrite_config_session_name(new_session)
            if session_exists(old_session) and old_session != new_session:
                rename_session(old_session, new_session)
        except Exception as e:
            # Roll the registry change back so we don't leave a project whose
            # launch is permanently broken.
            try:
                registry.remove(new_name)
                self.project.name = old_name
                registry.add(self.project)
                self._rewrite_config_session_name(old_session)
            except Exception:
                pass
            self.app.notify(f"Failed to rename: {e}", severity="error")
            self.dismiss(None)
            return

        self.app.notify(f"Renamed to: {new_name}", title="Success")
        self.dismiss("renamed")

    def _rewrite_config_session_name(self, session_name: str) -> None:
        """Rewrite the ``session_name:`` key in the project's .kata.yaml.

        No-op if the config file doesn't exist yet (launch will fall back to the
        sanitized project name). Raises on read/write failure so the caller can
        roll back.
        """
        import yaml

        config_path = get_project_config_path(self.project.path)
        if not config_path.exists():
            return
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        data["session_name"] = session_name
        config_path.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def action_move_group(self) -> None:
        """Move project to a different group."""
        self.app.push_screen(
            GroupSelectorDialog(
                current_group=self.project.group,
            ),
            self._on_group_selected,
        )

    def _on_group_selected(self, group: str | None) -> None:
        """Handle group selection."""
        if not group or group == self.project.group:
            return

        try:
            self.project.group = group
            registry = get_registry()
            registry.update(self.project)
            self.app.notify(f"Moved to group: {group}", title="Success")
            self.dismiss("moved")
        except Exception as e:
            self.app.notify(f"Failed to move: {e}", severity="error")
            self.dismiss(None)

    def action_open_terminal(self) -> None:
        """Open project directory in a new terminal window (in a worker thread)."""
        project_path = self.project.path
        system = platform.system()

        if system not in ("Darwin", "Linux"):
            self.app.notify("Unsupported platform", severity="error")
            self.dismiss(None)
            return

        def _work() -> None:
            try:
                if system == "Darwin":
                    self._open_macos_terminal(project_path)
                else:
                    self._open_linux_terminal(project_path)
            except Exception as e:
                self.app.call_from_thread(
                    self.app.notify,
                    f"Failed to open terminal: {e}",
                    severity="error",
                )
                self.app.call_from_thread(self.dismiss, None)
                return
            self.app.call_from_thread(
                self.app.notify,
                f"Opened terminal at: {project_path}",
                title="Success",
            )
            self.app.call_from_thread(self.dismiss, "terminal_opened")

        self.run_worker(_work, thread=True, exclusive=True, group="terminal")

    @staticmethod
    def _escape_applescript(text: str) -> str:
        """Escape a string for safe embedding inside an AppleScript literal."""
        return text.replace("\\", "\\\\").replace('"', '\\"')

    def _open_macos_terminal(self, path: str) -> None:
        """Open terminal on macOS (runs in a worker thread)."""
        safe_path = self._escape_applescript(path)

        # Check if iTerm2 is available
        iterm_check = subprocess.run(
            ["osascript", "-e", 'id of app "iTerm"'],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

        if iterm_check.returncode == 0:
            # Use iTerm2
            script = f"""
            tell application "iTerm"
                create window with default profile
                tell current session of current window
                    write text "cd \\"{safe_path}\\""
                end tell
            end tell
            """
        else:
            # Fall back to Terminal.app
            script = f"""
            tell application "Terminal"
                do script "cd \\"{safe_path}\\""
                activate
            end tell
            """
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
        )

    def _open_linux_terminal(self, path: str) -> None:
        """Open terminal on Linux (runs in a worker thread)."""
        quoted = shlex.quote(path)
        shell_cmd = f'cd {quoted} && exec "$SHELL"'
        # Try common terminal emulators. For -e style launchers the command must
        # be run through a shell so `cd` (a builtin) actually works.
        terminals = [
            ["gnome-terminal", "--working-directory", path],
            ["konsole", "--workdir", path],
            ["xfce4-terminal", f"--working-directory={path}"],
            ["x-terminal-emulator", "-e", "sh", "-c", shell_cmd],
            ["xterm", "-e", "sh", "-c", shell_cmd],
        ]

        for cmd in terminals:
            try:
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except FileNotFoundError:
                continue

        raise RuntimeError("No supported terminal emulator found")

    def action_browse_files(self) -> None:
        """Close the menu and let the app open the file browser.

        The browser is a full-screen modal; opening it from here would stack it
        on the dismissing menu, so we hand the request back to the app via the
        dismiss result (see ``KataDashboard._on_context_menu_result``).
        """
        self.dismiss("browse_files")

    def action_view_changes(self) -> None:
        """Close the menu and let the app open the diff viewer (same pattern
        as ``action_browse_files``)."""
        self.dismiss("view_changes")

    def action_open_workspace(self) -> None:
        """Close the menu and let the app open the workspace (same pattern
        as ``action_browse_files``)."""
        self.dismiss("open_workspace")

    def action_save_layout(self) -> None:
        """Save the current session layout to the project's config (in a worker)."""
        # Show a loading indicator on the menu while the (multi-subprocess)
        # capture runs off the UI thread.
        try:
            self.query_one("#menu-subtitle", Static).update(
                f"[dim]{self.project.name}[/dim]  [yellow]saving layout…[/yellow]"
            )
        except Exception:
            pass

        project = self.project

        def _work() -> None:
            try:
                config_path = save_current_session_layout(project)
            except SessionError as e:
                self.app.call_from_thread(
                    self.app.notify, f"Failed to save layout: {e}", severity="error"
                )
                self.app.call_from_thread(self.dismiss, None)
                return
            self.app.call_from_thread(
                self.app.notify, f"Layout saved: {config_path.name}", title="Success"
            )
            self.app.call_from_thread(self.dismiss, "layout_saved")

        self.run_worker(_work, thread=True, exclusive=True, group="save_layout")

    def action_set_shortcut(self) -> None:
        """Set a quick launch shortcut (1-9) for this project."""
        self.app.push_screen(
            ShortcutSelectorDialog(
                current_shortcut=self.project.shortcut,
                project_name=self.project.name,
            ),
            self._on_shortcut_selected,
        )

    def action_toggle_notifications(self) -> None:
        """Toggle notifications for this project."""
        settings = get_settings()
        disabled = list(settings.notifications_disabled_projects)
        project_name = self.project.name

        if project_name in disabled:
            disabled.remove(project_name)
            update_settings(notifications_disabled_projects=disabled)
            self.app.notify(f"Notifications enabled for {project_name}", title="Notifications")
        else:
            disabled.append(project_name)
            update_settings(notifications_disabled_projects=disabled)
            self.app.notify(f"Notifications disabled for {project_name}", title="Notifications")

        self.dismiss("notifications_toggled")

    def action_set_color(self) -> None:
        """Set or clear the project's color."""
        self.app.push_screen(
            ColorSelectorDialog(
                current_color=self.project.color,
                project_name=self.project.name,
            ),
            self._on_color_selected,
        )

    def _on_color_selected(self, color: str | None) -> None:
        """Handle color selection."""
        # None means cancelled, "clear" means remove color
        if color is None:
            return

        try:
            registry = get_registry()

            session_name = session_name_for(self.project)

            if color == "clear":
                self.project.color = None
                registry.update(self.project)
                self.app.notify("Color cleared", title="Success")
                self._apply_color_async(session_name, None)
            else:
                self.project.color = color
                registry.update(self.project)
                self.app.notify(f"Color set to: {color}", title="Success")
                self._apply_color_async(session_name, color)

            self.dismiss("color_changed")
        except Exception as e:
            self.app.notify(f"Failed to set color: {e}", severity="error")
            self.dismiss(None)

    def _apply_color_async(self, session_name: str, color: str | None) -> None:
        """Apply or clear tmux styling off the UI thread via direct, safe calls.

        Uses the subprocess-based ``kata.services.tmux_style`` helpers directly
        (any project name is safe) instead of interpolating the name into a
        ``tmux run-shell`` command string.
        """

        def _work() -> None:
            try:
                if color is None:
                    clear_project_color(session_name)
                else:
                    apply_project_color(session_name, color)
            except Exception:
                pass

        self.run_worker(_work, thread=True, exclusive=False, group="tmux_style")

    def _on_shortcut_selected(self, shortcut: int | None) -> None:
        """Handle shortcut selection."""
        # None means cancelled, -1 means clear shortcut
        if shortcut is None:
            return

        try:
            registry = get_registry()

            # If clearing shortcut
            if shortcut == -1:
                self.project.shortcut = None
                registry.update(self.project)
                self.app.notify("Shortcut cleared", title="Success")
                self.dismiss("shortcut_changed")
                return

            # Check if shortcut is already used by another project
            for project in registry.list_all():
                if project.shortcut == shortcut and project.name != self.project.name:
                    self.app.notify(
                        f"Shortcut {shortcut} already used by '{project.name}'",
                        severity="error",
                    )
                    return

            self.project.shortcut = shortcut
            registry.update(self.project)
            self.app.notify(f"Shortcut set to: {shortcut}", title="Success")
            self.dismiss("shortcut_changed")
        except Exception as e:
            self.app.notify(f"Failed to set shortcut: {e}", severity="error")
            self.dismiss(None)
