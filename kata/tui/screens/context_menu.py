"""Context Menu screen for project actions."""

import platform
import subprocess
from enum import Enum, auto

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, OptionList, Static
from textual.widgets.option_list import Option

from kata.core.models import Project
from kata.services.registry import get_registry
from kata.services.sessions import (
    SessionNotFoundError,
    get_session_status,
    kill_session,
    session_exists,
)


class MenuAction(Enum):
    """Available context menu actions."""

    KILL = auto()
    DELETE = auto()
    RENAME = auto()
    MOVE_GROUP = auto()
    OPEN_TERMINAL = auto()


class ContextMenuScreen(ModalScreen[str | None]):
    """Modal context menu for project actions."""

    CSS = """
    ContextMenuScreen {
        align: center middle;
    }

    ContextMenuScreen #menu-container {
        width: 36;
        height: auto;
        max-height: 16;
        background: $surface;
        border: solid $surface-lighten-1;
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
        background: $surface-lighten-1;
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
            yield Static("Project Actions", id="menu-title")
            yield Static(f"[dim]{self.project.name}[/dim]", id="menu-subtitle")

            options = [
                Option("[k] Kill Session", id="kill"),
                Option("[d] Delete Project", id="delete"),
                Option("[r] Rename Project", id="rename"),
                Option("[g] Move to Group", id="move_group"),
                Option("[t] Open in Terminal", id="open_terminal"),
            ]
            yield OptionList(*options, id="menu-list")

    def on_mount(self) -> None:
        """Handle mount - execute preselected action if any."""
        if self.preselected_action:
            # Execute the preselected action immediately
            self.set_timer(0.1, self._execute_preselected)

    def _execute_preselected(self) -> None:
        """Execute the preselected action."""
        if self.preselected_action == MenuAction.KILL:
            self.action_kill_session()
        elif self.preselected_action == MenuAction.DELETE:
            self.action_delete_project()

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection."""
        option_id = event.option.id
        if option_id == "kill":
            self.action_kill_session()
        elif option_id == "delete":
            self.action_delete_project()
        elif option_id == "rename":
            self.action_rename_project()
        elif option_id == "move_group":
            self.action_move_group()
        elif option_id == "open_terminal":
            self.action_open_terminal()

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

        if not session_exists(self.project.name):
            self.app.notify("No active session to kill", severity="warning")
            self.dismiss(None)
            return

        try:
            kill_session(self.project.name)
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

        try:
            # Remove old entry and add with new name
            old_name = self.project.name
            registry.remove(old_name)

            self.project.name = new_name
            self.project.config = f"{new_name}.yaml"
            registry.add(self.project)

            self.app.notify(f"Renamed to: {new_name}", title="Success")
            self.dismiss("renamed")
        except Exception as e:
            self.app.notify(f"Failed to rename: {e}", severity="error")
            self.dismiss(None)

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
        """Open project directory in a new terminal window."""
        project_path = self.project.path

        try:
            if platform.system() == "Darwin":
                # macOS: Try iTerm2 first, fall back to Terminal.app
                self._open_macos_terminal(project_path)
            elif platform.system() == "Linux":
                self._open_linux_terminal(project_path)
            else:
                self.app.notify("Unsupported platform", severity="error")
                self.dismiss(None)
                return

            self.app.notify(f"Opened terminal at: {project_path}", title="Success")
            self.dismiss("terminal_opened")
        except Exception as e:
            self.app.notify(f"Failed to open terminal: {e}", severity="error")
            self.dismiss(None)

    def _open_macos_terminal(self, path: str) -> None:
        """Open terminal on macOS."""
        # Check if iTerm2 is available
        iterm_check = subprocess.run(
            ["osascript", "-e", 'id of app "iTerm"'],
            capture_output=True,
        )

        if iterm_check.returncode == 0:
            # Use iTerm2
            script = f'''
            tell application "iTerm"
                create window with default profile
                tell current session of current window
                    write text "cd {path}"
                end tell
            end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True)
        else:
            # Fall back to Terminal.app
            script = f'''
            tell application "Terminal"
                do script "cd {path}"
                activate
            end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True)

    def _open_linux_terminal(self, path: str) -> None:
        """Open terminal on Linux."""
        # Try common terminal emulators
        terminals = [
            ["gnome-terminal", "--working-directory", path],
            ["konsole", "--workdir", path],
            ["xfce4-terminal", f"--working-directory={path}"],
            ["xterm", "-e", f"cd {path} && $SHELL"],
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


class ConfirmDialog(ModalScreen[bool]):
    """Simple confirmation dialog."""

    CSS = """
    ConfirmDialog {
        align: center middle;
    }

    ConfirmDialog #dialog-container {
        width: 36;
        height: auto;
        background: $surface;
        border: solid $surface-lighten-1;
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
        background: $surface-lighten-1;
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
        border: thick $primary;
        padding: 1 2;
    }

    InputDialog #dialog-title {
        text-style: bold;
        color: $primary;
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
        from textual.containers import Horizontal

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
        border: thick $primary;
        padding: 1 2;
    }

    GroupSelectorDialog #dialog-title {
        text-style: bold;
        color: $primary;
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
        from textual.containers import Horizontal

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
