"""TUI application for Kata dashboard."""

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import Footer, Header, Static

from kata.core.models import Project
from kata.core.settings import get_settings, reload_settings
from kata.services.registry import get_registry
from kata.services.sessions import kill_session, launch_or_attach, launch_or_attach_adhoc, session_exists
from kata.tui.screens.context_menu import ContextMenuScreen, MenuAction
from kata.tui.screens.search import SearchModal
from kata.tui.screens.settings import SettingsScreen
from kata.tui.screens.wizard import AddWizard
from kata.tui.themes import KATA_THEMES
from kata.tui.widgets.preview import PreviewPane
from kata.tui.widgets.recents import RecentsPanel
from kata.tui.widgets.tree import ProjectTree
from kata.utils.zoxide import ZoxideEntry


class EmptyState(Static):
    """Widget shown when no projects are registered."""

    DEFAULT_CSS = """
    EmptyState {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose empty state message."""
        yield Static(
            "[dim]No projects registered yet.[/dim]\n\n"
            "Use [bold]kata add[/bold] to add a project.",
            markup=True,
        )


class KataDashboard(App):
    """Main TUI application for Kata."""

    TITLE = "▸ kata"
    SUB_TITLE = "workspace orchestrator"
    ENABLE_COMMAND_PALETTE = False

    # Register custom Kata themes
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Register all Kata themes
        for theme in KATA_THEMES:
            self.register_theme(theme)
        # Reload settings fresh from disk to get current theme
        settings = reload_settings()
        theme_name = settings.theme
        if theme_name in [t.name for t in KATA_THEMES]:
            self.theme = theme_name
        else:
            self.theme = "kata-dark"

    CSS = """
    Screen {
        background: $background;
    }

    Header {
        dock: top;
        height: 1;
        background: $background;
        color: $text-muted;
    }

    Header HeaderTitle {
        color: $primary;
        text-style: bold;
    }

    #main-container {
        width: 100%;
        height: 100%;
    }

    #content-area {
        width: 100%;
        height: 1fr;
    }

    #tree-container {
        width: 35;
        height: 100%;
        border-right: vkey $surface-lighten-1;
    }

    #preview-container {
        width: 1fr;
        height: 100%;
        padding: 1 2;
    }

    #recents-container {
        width: 100%;
        height: 12;
        display: block;
        border-top: solid $surface-lighten-1;
    }

    #recents-container.-hidden {
        display: none;
    }

    Footer {
        height: 1;
        background: $background;
        color: $text-muted;
    }

    Footer > .footer--highlight {
        background: transparent;
        color: $text-muted;
    }

    Footer > .footer--key {
        background: transparent;
        color: $primary;
        text-style: bold;
    }

    Footer > .footer--description {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("enter", "launch", "Launch"),
        Binding("a", "add_project", "Add"),
        Binding("e", "edit_project", "Edit"),
        Binding("r", "refresh", "Refresh"),
        Binding("/", "search", "Search"),
        Binding("?", "help", "Help"),
        Binding("m", "context_menu", "Menu"),
        Binding("s", "settings", "Settings"),
        Binding("k", "quick_kill", "Kill", show=False),
        Binding("d", "quick_delete", "Delete", show=False),
        Binding("tab", "switch_section", "Switch Section", show=False),
        Binding("[", "focus_projects", "Projects"),
        Binding("]", "focus_recents", "Recents"),
        Binding("1", "launch_shortcut_1", "1", show=False),
        Binding("2", "launch_shortcut_2", "2", show=False),
        Binding("3", "launch_shortcut_3", "3", show=False),
        Binding("4", "launch_shortcut_4", "4", show=False),
        Binding("5", "launch_shortcut_5", "5", show=False),
        Binding("6", "launch_shortcut_6", "6", show=False),
        Binding("7", "launch_shortcut_7", "7", show=False),
        Binding("8", "launch_shortcut_8", "8", show=False),
        Binding("9", "launch_shortcut_9", "9", show=False),
    ]

    _project_to_launch: Project | None = None
    _zoxide_to_launch: ZoxideEntry | None = None
    _refresh_timer: Timer | None = None
    _explicit_quit: bool = False
    _focus_on_recents: bool = False

    def compose(self) -> ComposeResult:
        """Compose the dashboard."""
        yield Header()

        registry = get_registry()
        if len(registry) == 0:
            yield Container(EmptyState(), id="main-container")
        else:
            yield Container(
                Vertical(
                    Horizontal(
                        Container(ProjectTree(), id="tree-container"),
                        Container(PreviewPane(), id="preview-container"),
                        id="content-area",
                    ),
                    Container(RecentsPanel(), id="recents-container"),
                ),
                id="main-container",
            )

        yield Footer()

    def on_mount(self) -> None:
        """Start status refresh timer using settings."""
        settings = get_settings()
        self._refresh_timer = self.set_interval(
            float(settings.refresh_interval), self._refresh_status
        )
        # Trigger immediate status refresh on startup after first paint
        self.call_after_refresh(self._initial_status_refresh)
        # Update preview with first project after tree loads and status is updated
        self.set_timer(0.3, self._show_first_project)

    def _initial_status_refresh(self) -> None:
        """Refresh status after initial UI render."""
        # Small delay to ensure tmux server is accessible
        self.set_timer(0.05, self._refresh_status)

    def _show_first_project(self) -> None:
        """Show the first project in the preview pane."""
        try:
            tree = self.query_one(ProjectTree)
            project = tree.get_selected_project()
            if project:
                preview = self.query_one(PreviewPane)
                preview.update_project(project)
        except Exception:
            pass

    def on_unmount(self) -> None:
        """Stop status refresh timer."""
        if self._refresh_timer:
            self._refresh_timer.stop()

    def _refresh_status(self) -> None:
        """Refresh status indicators periodically."""
        try:
            preview = self.query_one(PreviewPane)
            preview.refresh_status()
            tree = self.query_one(ProjectTree)
            tree.refresh_projects()
        except Exception:
            pass

    def action_quit(self) -> None:
        """Quit the application (explicitly, breaking the loop)."""
        self._explicit_quit = True
        self.exit()

    def action_refresh(self) -> None:
        """Refresh the project tree."""
        try:
            tree = self.query_one(ProjectTree)
            tree.refresh_projects()
            self.notify("Refreshed project list")
        except Exception:
            pass

    def action_search(self) -> None:
        """Open search modal."""
        self.push_screen(SearchModal(), self._on_search_result)

    def _on_search_result(self, result: Project | ZoxideEntry | None) -> None:
        """Handle search modal result."""
        if result is None:
            return

        if isinstance(result, Project):
            result.record_open()
            registry = get_registry()
            registry.update(result)
            self._project_to_launch = result
            self.exit()
        elif isinstance(result, ZoxideEntry):
            self._zoxide_to_launch = result
            self.exit()

    def action_launch(self) -> None:
        """Launch the selected project or zoxide entry."""
        try:
            # If focused on recents, launch from there
            if self._focus_on_recents:
                recents = self.query_one(RecentsPanel)
                entry = recents.get_selected_entry()
                if entry:
                    self._zoxide_to_launch = entry
                    self.exit()
                return

            tree = self.query_one(ProjectTree)

            # Check for project first
            project = tree.get_selected_project()
            if project:
                project.record_open()
                registry = get_registry()
                registry.update(project)
                self._project_to_launch = project
                self.exit()
                return

            # Check for zoxide entry
            zoxide_entry = tree.get_selected_zoxide()
            if zoxide_entry:
                self._zoxide_to_launch = zoxide_entry
                self.exit()
        except Exception:
            pass

    def action_help(self) -> None:
        """Show help."""
        self.notify(
            "Enter: Launch | Tab: Switch | a: Add | e: Edit | m: Menu | /: Search | q: Quit",
            title="Keyboard Shortcuts",
        )

    def action_context_menu(self) -> None:
        """Open context menu for selected project."""
        try:
            tree = self.query_one(ProjectTree)
            project = tree.get_selected_project()

            if not project:
                self.notify("No project selected", severity="warning")
                return

            self.push_screen(ContextMenuScreen(project), self._on_context_menu_result)
        except Exception:
            pass

    def _on_context_menu_result(self, result: str | None) -> None:
        """Handle context menu result."""
        if result in ("deleted", "renamed", "moved", "shortcut_changed"):
            # Refresh the tree after modifications
            try:
                tree = self.query_one(ProjectTree)
                tree.refresh_projects()
            except Exception:
                pass

    def action_settings(self) -> None:
        """Open settings screen."""
        self.push_screen(SettingsScreen(), self._on_settings_closed)

    def _on_settings_closed(self, result: None) -> None:
        """Handle settings screen close."""
        pass

    def action_switch_section(self) -> None:
        """Switch focus between projects tree and recents section."""
        try:
            if self._focus_on_recents:
                self.action_focus_projects()
            else:
                self.action_focus_recents()
        except Exception:
            pass

    def action_focus_projects(self) -> None:
        """Focus the projects tree."""
        try:
            tree = self.query_one(ProjectTree)
            tree._focus_tree()
            self._focus_on_recents = False
        except Exception:
            pass

    def action_focus_recents(self) -> None:
        """Focus the recents panel."""
        try:
            recents = self.query_one(RecentsPanel)
            recents.focus_list()
            self._focus_on_recents = True
        except Exception:
            pass

    def _launch_by_shortcut(self, shortcut: int) -> None:
        """Launch project by shortcut number."""
        registry = get_registry()
        for project in registry.list_all():
            if project.shortcut == shortcut:
                project.record_open()
                registry.update(project)
                self._project_to_launch = project
                self.exit()
                return
        self.notify(f"No project with shortcut {shortcut}", severity="warning")

    def action_launch_shortcut_1(self) -> None:
        self._launch_by_shortcut(1)

    def action_launch_shortcut_2(self) -> None:
        self._launch_by_shortcut(2)

    def action_launch_shortcut_3(self) -> None:
        self._launch_by_shortcut(3)

    def action_launch_shortcut_4(self) -> None:
        self._launch_by_shortcut(4)

    def action_launch_shortcut_5(self) -> None:
        self._launch_by_shortcut(5)

    def action_launch_shortcut_6(self) -> None:
        self._launch_by_shortcut(6)

    def action_launch_shortcut_7(self) -> None:
        self._launch_by_shortcut(7)

    def action_launch_shortcut_8(self) -> None:
        self._launch_by_shortcut(8)

    def action_launch_shortcut_9(self) -> None:
        self._launch_by_shortcut(9)

    @on(SettingsScreen.SettingsChanged)
    def on_settings_changed(self, event: SettingsScreen.SettingsChanged) -> None:
        """Handle settings changes."""
        # Update refresh timer with new interval
        if self._refresh_timer:
            self._refresh_timer.stop()
        self._refresh_timer = self.set_interval(
            float(event.settings.refresh_interval), self._refresh_status
        )

    def action_quick_kill(self) -> None:
        """Quick kill - open context menu with kill pre-selected."""
        try:
            tree = self.query_one(ProjectTree)
            project = tree.get_selected_project()

            if not project:
                self.notify("No project selected", severity="warning")
                return

            self.push_screen(
                ContextMenuScreen(project, preselected=MenuAction.KILL),
                self._on_context_menu_result,
            )
        except Exception:
            pass

    def action_quick_delete(self) -> None:
        """Quick delete - open context menu with delete pre-selected."""
        try:
            tree = self.query_one(ProjectTree)
            project = tree.get_selected_project()

            if not project:
                self.notify("No project selected", severity="warning")
                return

            self.push_screen(
                ContextMenuScreen(project, preselected=MenuAction.DELETE),
                self._on_context_menu_result,
            )
        except Exception:
            pass

    def action_add_project(self) -> None:
        """Open the Add Project wizard (pre-filled with zoxide path if selected)."""
        try:
            # Check recents panel first if focused there
            if self._focus_on_recents:
                recents = self.query_one(RecentsPanel)
                entry = recents.get_selected_entry()
                if entry:
                    self.push_screen(AddWizard(initial_path=entry.path), self._on_wizard_complete)
                    return

            # Check tree for zoxide entry
            tree = self.query_one(ProjectTree)
            zoxide_entry = tree.get_selected_zoxide()

            if zoxide_entry:
                self.push_screen(AddWizard(initial_path=zoxide_entry.path), self._on_wizard_complete)
            else:
                self.push_screen(AddWizard(), self._on_wizard_complete)
        except Exception:
            self.push_screen(AddWizard(), self._on_wizard_complete)

    def _on_wizard_complete(self, result: Project | None) -> None:
        """Handle wizard completion."""
        if result:
            self.notify(f"Added project: {result.name}", title="Success")
            # Refresh the tree
            try:
                tree = self.query_one(ProjectTree)
                tree.refresh_projects()
            except Exception:
                pass

    def action_edit_project(self) -> None:
        """Edit the selected project's config."""
        import subprocess
        import shutil
        import os

        try:
            tree = self.query_one(ProjectTree)
            project = tree.get_selected_project()

            if not project:
                self.notify("No project selected", severity="warning")
                return

            from kata.core.templates import get_template_path

            config_path = get_template_path(project)

            if not config_path.exists():
                self.notify("Config file not found", severity="error")
                return

            # Get editor
            editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
            if not editor:
                for fallback in ["nano", "vim", "vi"]:
                    if shutil.which(fallback):
                        editor = fallback
                        break

            if not editor:
                self.notify("No editor found. Set $EDITOR", severity="error")
                return

            # Suspend app and open editor
            with self.suspend():
                subprocess.run([editor, str(config_path)])

        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    @on(ProjectTree.ProjectSelected)
    def on_project_selected(self, event: ProjectTree.ProjectSelected) -> None:
        """Handle project selection from tree."""
        project = event.project
        project.record_open()
        registry = get_registry()
        registry.update(project)

        self._project_to_launch = project
        self.exit()

    @on(ProjectTree.ZoxideSelected)
    def on_zoxide_selected(self, event: ProjectTree.ZoxideSelected) -> None:
        """Handle zoxide entry selection from tree."""
        self._zoxide_to_launch = event.entry
        self.exit()

    @on(RecentsPanel.RecentSelected)
    def on_recent_selected(self, event: RecentsPanel.RecentSelected) -> None:
        """Handle recent entry selection from recents panel."""
        self._zoxide_to_launch = event.entry
        self.exit()

    @on(RecentsPanel.AddRequested)
    def on_add_requested(self, event: RecentsPanel.AddRequested) -> None:
        """Handle add request from recents panel."""
        self.push_screen(AddWizard(initial_path=event.entry.path), self._on_wizard_complete)

    def on_project_tree_project_highlighted(
        self, event: ProjectTree.ProjectHighlighted
    ) -> None:
        """Handle project highlight (cursor movement)."""
        preview = self.query_one(PreviewPane)
        preview.update_project(event.project)

def run_dashboard() -> None:
    """Run the Kata dashboard."""
    app = KataDashboard()
    app.run()

    # After the app exits, launch the selected project or zoxide entry
    project = app._project_to_launch
    zoxide_entry = app._zoxide_to_launch

    if project:
        try:
            launch_or_attach(project)
        except Exception as e:
            print(f"Error: {e}")
    elif zoxide_entry:
        try:
            launch_or_attach_adhoc(zoxide_entry.path)
        except Exception as e:
            print(f"Error: {e}")
