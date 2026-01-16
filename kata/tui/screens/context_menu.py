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
    SessionError,
    SessionNotFoundError,
    get_session_status,
    kill_session,
    save_current_session_layout,
    session_exists,
)


class MenuAction(Enum):
    """Available context menu actions."""

    KILL = auto()
    DELETE = auto()
    RENAME = auto()
    MOVE_GROUP = auto()
    OPEN_TERMINAL = auto()
    SAVE_LAYOUT = auto()
    SET_SHORTCUT = auto()


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
        Binding("l", "save_layout", "Save Layout", show=False),
        Binding("s", "set_shortcut", "Set Shortcut", show=False),
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

            # Show current shortcut if set
            shortcut_label = "(s) Set Shortcut"
            if self.project.shortcut:
                shortcut_label = f"(s) Set Shortcut [dim](current: {self.project.shortcut})[/dim]"

            options = [
                Option("(k) Kill Session", id="kill"),
                Option("(d) Delete Project", id="delete"),
                Option("(r) Rename Project", id="rename"),
                Option("(g) Move to Group", id="move_group"),
                Option("(t) Open in Terminal", id="open_terminal"),
                Option("(l) Save Layout", id="save_layout"),
                Option(shortcut_label, id="set_shortcut"),
            ]
            yield OptionList(*options, id="menu-list")

    def on_mount(self) -> None:
        """Handle mount - execute preselected action if any."""
        if self.preselected_action:
            # Highlight the preselected option in the list
            action_to_index = {
                MenuAction.KILL: 0,
                MenuAction.DELETE: 1,
                MenuAction.RENAME: 2,
                MenuAction.MOVE_GROUP: 3,
                MenuAction.OPEN_TERMINAL: 4,
                MenuAction.SAVE_LAYOUT: 5,
                MenuAction.SET_SHORTCUT: 6,
            }
            index = action_to_index.get(self.preselected_action, 0)
            try:
                menu_list = self.query_one("#menu-list", OptionList)
                menu_list.highlighted = index
            except Exception:
                pass
            # Execute the preselected action immediately
            self.set_timer(0.1, self._execute_preselected)

    def _execute_preselected(self) -> None:
        """Execute the preselected action."""
        if self.preselected_action == MenuAction.KILL:
            self.action_kill_session()
        elif self.preselected_action == MenuAction.DELETE:
            self.action_delete_project()
        elif self.preselected_action == MenuAction.RENAME:
            self.action_rename_project()
        elif self.preselected_action == MenuAction.MOVE_GROUP:
            self.action_move_group()
        elif self.preselected_action == MenuAction.OPEN_TERMINAL:
            self.action_open_terminal()
        elif self.preselected_action == MenuAction.SAVE_LAYOUT:
            self.action_save_layout()
        elif self.preselected_action == MenuAction.SET_SHORTCUT:
            self.action_set_shortcut()

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
        elif option_id == "save_layout":
            self.action_save_layout()
        elif option_id == "set_shortcut":
            self.action_set_shortcut()

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

    def action_save_layout(self) -> None:
        """Save the current session layout to the project's config."""
        if not session_exists(self.project.name):
            self.app.notify(
                "No active session to save",
                severity="warning",
            )
            self.dismiss(None)
            return

        try:
            config_path = save_current_session_layout(self.project)
            self.app.notify(
                f"Layout saved: {config_path.name}",
                title="Success",
            )
            self.dismiss("layout_saved")
        except SessionError as e:
            self.app.notify(f"Failed to save layout: {e}", severity="error")
            self.dismiss(None)

    def action_set_shortcut(self) -> None:
        """Set a quick launch shortcut (1-9) for this project."""
        self.app.push_screen(
            ShortcutSelectorDialog(
                current_shortcut=self.project.shortcut,
                project_name=self.project.name,
            ),
            self._on_shortcut_selected,
        )

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
        border: solid $surface-lighten-1;
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
        border: solid $surface-lighten-1;
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
        border: solid $surface-lighten-1;
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
        background: $surface-lighten-1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("1", "select_1", "1", show=False),
        Binding("2", "select_2", "2", show=False),
        Binding("3", "select_3", "3", show=False),
        Binding("4", "select_4", "4", show=False),
        Binding("5", "select_5", "5", show=False),
        Binding("6", "select_6", "6", show=False),
        Binding("7", "select_7", "7", show=False),
        Binding("8", "select_8", "8", show=False),
        Binding("9", "select_9", "9", show=False),
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
            yield Static(f"[dim]Press 1-9 or select below[/dim]", id="dialog-subtitle")

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
            except ValueError:
                self.dismiss(None)

    def action_cancel(self) -> None:
        """Handle escape key."""
        self.dismiss(None)

    def action_clear_shortcut(self) -> None:
        """Clear shortcut (0 key)."""
        self.dismiss(-1)

    def action_select_1(self) -> None:
        self.dismiss(1)

    def action_select_2(self) -> None:
        self.dismiss(2)

    def action_select_3(self) -> None:
        self.dismiss(3)

    def action_select_4(self) -> None:
        self.dismiss(4)

    def action_select_5(self) -> None:
        self.dismiss(5)

    def action_select_6(self) -> None:
        self.dismiss(6)

    def action_select_7(self) -> None:
        self.dismiss(7)

    def action_select_8(self) -> None:
        self.dismiss(8)

    def action_select_9(self) -> None:
        self.dismiss(9)
