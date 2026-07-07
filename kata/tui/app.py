"""TUI application for Kata dashboard."""

import logging

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import Footer, Static

from kata import __version__
from kata.core.models import Project
from kata.core.settings import get_settings, reload_settings
from kata.services.registry import get_registry
from kata.services.sessions import (
    launch_or_attach,
    launch_or_attach_adhoc,
)
from kata.tui.screens.context_menu import ContextMenuScreen, MenuAction
from kata.tui.screens.notification_center import NotificationCenterModal
from kata.tui.screens.search import SearchModal
from kata.tui.screens.settings import SettingsScreen
from kata.tui.screens.switcher import SwitcherModal
from kata.tui.screens.wizard import AddWizard
from kata.tui.themes import KATA_THEMES
from kata.tui.widgets.preview import PreviewPane
from kata.tui.widgets.recents import RecentsPanel
from kata.tui.widgets.tree import ProjectTree
from kata.utils.zoxide import ZoxideEntry

logger = logging.getLogger(__name__)

KATA_BANNER_LINES = [
    "[#22d3ee]█▄▀[/]  [#38bdf8]▄▀▄[/]  [#818cf8]▀█▀[/]  [#a78bfa]▄▀▄[/]",
    "[#22d3ee]█ █[/]  [#38bdf8]█▀█[/]   [#818cf8]█[/]   [#a78bfa]█▀█[/]",
    "[#22d3ee]▀ ▀[/]  [#38bdf8]▀ ▀[/]   [#818cf8]▀[/]   [#a78bfa]▀ ▀[/]",
]


class KataBanner(Widget):
    """Custom ASCII art header banner with circuit-node aesthetic."""

    DEFAULT_CSS = """
    KataBanner {
        dock: top;
        width: 100%;
        height: 6;
        background: $background;
        border-bottom: tall $surface-lighten-1;
    }

    KataBanner #banner-art {
        width: 100%;
        height: 3;
        margin-top: 1;
        content-align: center middle;
        text-align: center;
    }

    KataBanner #banner-version {
        width: 100%;
        height: 1;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, version: str = "") -> None:
        super().__init__()
        self._version = version
        self._badge_count = 0

    def compose(self) -> ComposeResult:
        yield Static("\n".join(KATA_BANNER_LINES), id="banner-art", markup=True)
        yield Static(f"v{self._version}", id="banner-version")

    def update_badge(self, count: int) -> None:
        """Update the notification badge count."""
        self._badge_count = count
        try:
            version_widget = self.query_one("#banner-version", Static)
            if count > 0:
                version_widget.update(f"v{self._version}  │  󰂚 {count}")
            else:
                version_widget.update(f"v{self._version}")
        except Exception:
            pass


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
            "Press [bold]a[/bold] to add your first project.",
            markup=True,
        )


class KataDashboard(App):
    """Main TUI application for Kata."""

    TITLE = "▸ kata"
    SUB_TITLE = f"v{__version__}"
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

    #main-container {
        width: 100%;
        height: 100%;
    }

    #content-area {
        width: 100%;
        height: 1fr;
    }

    #tree-container {
        width: 38;
        height: 100%;
        border-right: vkey $surface-lighten-1;
    }

    #preview-container {
        width: 1fr;
        height: 100%;
        padding: 1 3;
    }

    #recents-container {
        width: 100%;
        height: 12;
        display: block;
        border-top: tall $surface-lighten-1;
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
        background: $surface;
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
        Binding("f", "browse_files", "Files"),
        Binding("g", "view_diff", "Diff"),
        Binding("w", "open_workspace", "Workspace"),
        Binding("s", "settings", "Settings"),
        Binding("n", "notifications", "Notifs"),
        Binding("k", "quick_kill", "Kill", show=False),
        Binding("d", "quick_delete", "Delete", show=False),
        Binding("tab", "switch_section", "Switch Section", show=False),
        Binding("ctrl+at", "quick_switch", "Switch", show=False),
        Binding("[", "focus_projects", "Projects"),
        Binding("]", "focus_recents", "Recents"),
        Binding("1", "launch_shortcut(1)", "1", show=False),
        Binding("2", "launch_shortcut(2)", "2", show=False),
        Binding("3", "launch_shortcut(3)", "3", show=False),
        Binding("4", "launch_shortcut(4)", "4", show=False),
        Binding("5", "launch_shortcut(5)", "5", show=False),
        Binding("6", "launch_shortcut(6)", "6", show=False),
        Binding("7", "launch_shortcut(7)", "7", show=False),
        Binding("8", "launch_shortcut(8)", "8", show=False),
        Binding("9", "launch_shortcut(9)", "9", show=False),
    ]

    _project_to_launch: Project | None = None
    _zoxide_to_launch: ZoxideEntry | None = None
    _refresh_timer: Timer | None = None
    _explicit_quit: bool = False
    _focus_on_recents: bool = False
    _notification_badge_count: int = 0
    _session_to_switch: str | None = None

    def compose(self) -> ComposeResult:
        """Compose the dashboard.

        The full layout is always composed; the EmptyState and the main layout
        are shown/hidden based on registry contents. This means adding the first
        project (from the wizard) can reveal the real dashboard without a
        restart — the ProjectTree already exists to refresh into.
        """
        yield KataBanner(version=__version__)

        yield Container(EmptyState(), id="empty-container")
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

    def _update_empty_state(self) -> None:
        """Show the EmptyState or the main layout based on registry contents."""
        try:
            is_empty = len(get_registry()) == 0
            self.query_one("#empty-container").display = is_empty
            self.query_one("#main-container").display = not is_empty
        except Exception:
            pass

    def on_mount(self) -> None:
        """Start status refresh timer using settings."""
        self._update_empty_state()
        settings = get_settings()
        self._refresh_timer = self.set_interval(
            float(settings.refresh_interval), self._refresh_status
        )
        # Kick off first background refresh immediately (non-blocking)
        self.call_after_refresh(self._refresh_status)

        # Prune old notifications on TUI startup
        try:
            from kata.services.notifications.store import get_notification_store

            store = get_notification_store()
            store.prune(
                max_age_days=settings.notifications_retention_days,
                max_count=settings.notifications_max_count,
            )
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

        # Refresh notification badge count
        try:
            from kata.services.notifications.store import get_notification_store

            store = get_notification_store()
            count = store.unread_count()
            if count != self._notification_badge_count:
                self._notification_badge_count = count
                banner = self.query_one(KataBanner)
                banner.update_badge(count)
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

            project = tree.get_selected_project()
            if project:
                project.record_open()
                registry = get_registry()
                registry.update(project)
                self._project_to_launch = project
                self.exit()
        except Exception:
            pass

    def action_help(self) -> None:
        """Show help — including the otherwise-hidden bindings."""
        self.notify(
            "Enter launch · Tab switch · a add · e edit · m menu · f files · g diff · / search\n"
            "w workspace · k kill · d delete · n notifs · s settings · r refresh\n"
            "[ projects · ] recents · 1-9 shortcuts · ctrl+space quick switch · q quit",
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
        if result == "browse_files":
            # The menu deferred to the app so the browser opens on the main
            # screen (not stacked on the dismissing modal).
            self.action_browse_files()
            return
        if result == "view_changes":
            self.action_view_diff()
            return
        if result == "open_workspace":
            self.action_open_workspace()
            return
        if result in (
            "deleted",
            "renamed",
            "moved",
            "shortcut_changed",
            "color_changed",
            "killed",
            "layout_saved",
        ):
            # Refresh the tree immediately so state (e.g. a killed session's dot)
            # updates without waiting for the next timer tick.
            try:
                tree = self.query_one(ProjectTree)
                tree.refresh_projects()
            except Exception:
                pass
            # A delete may have emptied the registry.
            if result == "deleted":
                self._update_empty_state()

    def action_browse_files(self) -> None:
        """Open the file browser for the selected project."""
        try:
            tree = self.query_one(ProjectTree)
            project = tree.get_selected_project()

            if not project:
                self.notify("No project selected", severity="warning")
                return

            from pathlib import Path

            from kata.tui.screens.file_browser import FileBrowserScreen

            root = Path(project.path)
            if not root.is_dir():
                self.notify("Project path not found", severity="error")
                return

            self.push_screen(FileBrowserScreen(root, title=project.name))
        except Exception:
            pass

    def action_view_diff(self) -> None:
        """Open the diff viewer for the selected project's uncommitted changes."""
        try:
            tree = self.query_one(ProjectTree)
            project = tree.get_selected_project()

            if not project:
                self.notify("No project selected", severity="warning")
                return

            from pathlib import Path

            from kata.tui.screens.diff_viewer import DiffViewerScreen

            root = Path(project.path)
            if not root.is_dir():
                self.notify("Project path not found", severity="error")
                return

            self.push_screen(DiffViewerScreen(root, title=project.name))
        except Exception:
            pass

    def action_open_workspace(self) -> None:
        """Open the mouse-first workspace for the selected project."""
        try:
            tree = self.query_one(ProjectTree)
            project = tree.get_selected_project()

            if not project:
                self.notify("No project selected", severity="warning")
                return

            from pathlib import Path

            from kata.tui.screens.workspace import WorkspaceScreen

            if not Path(project.path).is_dir():
                self.notify("Project path not found", severity="error")
                return

            self.push_screen(WorkspaceScreen(project))
        except Exception:
            pass

    def action_settings(self) -> None:
        """Open settings screen."""
        self.push_screen(SettingsScreen(), self._on_settings_closed)

    def _on_settings_closed(self, result: None) -> None:
        """Handle settings screen close."""
        pass

    def action_notifications(self) -> None:
        """Open notification center."""
        # Guard against re-entry (key propagation while modal is already open)
        if any(isinstance(s, NotificationCenterModal) for s in self.screen_stack):
            return
        self.push_screen(NotificationCenterModal(), self._on_notification_result)

    def _on_notification_result(self, result: str | None) -> None:
        """Handle notification center result (session name to switch to)."""
        if result is None:
            return
        # Store session name and exit — switch happens after app.run() returns
        self._session_to_switch = result
        self.exit()

    def on_descendant_focus(self, event) -> None:
        """Keep ``_focus_on_recents`` in sync with where focus actually is.

        The flag was previously only flipped by the focus actions, so clicking
        or tab-landing into the recents list left it stale — and Enter/`a` then
        acted on the wrong pane.
        """
        try:
            recents = self.query_one(RecentsPanel)
            focused = event.widget
            self._focus_on_recents = focused is recents or recents in focused.ancestors
        except Exception:
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

    def action_quick_switch(self) -> None:
        """Open the quick project switcher."""
        self.push_screen(SwitcherModal(), self._on_switcher_result)

    def _on_switcher_result(self, result: Project | None) -> None:
        """Handle switcher modal result."""
        if result is None:
            return
        result.record_open()
        registry = get_registry()
        registry.update(result)
        self._project_to_launch = result
        self.exit()

    def action_launch_shortcut(self, shortcut: int) -> None:
        """Launch the project bound to a numeric shortcut (1-9)."""
        registry = get_registry()
        for project in registry.list_all():
            if project.shortcut == shortcut:
                project.record_open()
                registry.update(project)
                self._project_to_launch = project
                self.exit()
                return
        self.notify(f"No project with shortcut {shortcut}", severity="warning")

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
        """Open the Add Project wizard (pre-filled from the recents panel if focused)."""
        try:
            # Pre-fill from the recents panel if the user is focused there.
            if self._focus_on_recents:
                recents = self.query_one(RecentsPanel)
                entry = recents.get_selected_entry()
                if entry:
                    self.push_screen(AddWizard(initial_path=entry.path), self._on_wizard_complete)
                    return

            self.push_screen(AddWizard(), self._on_wizard_complete)
        except Exception:
            self.push_screen(AddWizard(), self._on_wizard_complete)

    def _on_wizard_complete(self, result: Project | None) -> None:
        """Handle wizard completion."""
        if result:
            self.notify(f"Added project: {result.name}", title="Success")
            # Reveal the real layout (this may be the very first project) and
            # refresh the tree so the new project appears immediately.
            self._update_empty_state()
            try:
                tree = self.query_one(ProjectTree)
                tree.refresh_projects()
                self.call_after_refresh(tree._highlight_first_project)
            except Exception:
                pass

    def action_edit_project(self) -> None:
        """Edit the selected project's config."""
        import os
        import shutil
        import subprocess

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

    @on(RecentsPanel.RecentSelected)
    def on_recent_selected(self, event: RecentsPanel.RecentSelected) -> None:
        """Handle recent entry selection from recents panel."""
        self._zoxide_to_launch = event.entry
        self.exit()

    @on(RecentsPanel.AddRequested)
    def on_add_requested(self, event: RecentsPanel.AddRequested) -> None:
        """Handle add request from recents panel."""
        self.push_screen(AddWizard(initial_path=event.entry.path), self._on_wizard_complete)

    def on_project_tree_project_highlighted(self, event: ProjectTree.ProjectHighlighted) -> None:
        """Handle project highlight (cursor movement)."""
        preview = self.query_one(PreviewPane)
        preview.update_project(event.project)


def launch_pending_target(app: "KataDashboard", *, interactive: bool = False) -> None:
    """Launch whatever the dashboard queued before exiting.

    Shared by ``run_dashboard`` and the return loop so the post-exit launch
    logic — and its error reporting — lives in exactly one place. Errors are
    always printed for the user (previously ``run_dashboard`` only logged them,
    so a failed launch left the user staring at a bare shell); ``interactive``
    additionally waits for Enter so the message survives a re-launch.

    Args:
        app: The exited dashboard instance.
        interactive: If True, pause for Enter after printing an error.
    """
    from kata.services.sessions import attach_session

    def _report(message: str, exc: Exception) -> None:
        logger.error(message, exc_info=exc)
        print(f"\n[Kata] Error: {exc}")
        if interactive:
            print("[Kata] Press Enter to continue...")
            try:
                input()
            except EOFError:
                pass

    project = app._project_to_launch
    zoxide_entry = app._zoxide_to_launch
    session_to_switch = app._session_to_switch

    if project:
        try:
            launch_or_attach(project)
        except Exception as e:
            _report(f"Failed to launch project {project.name}", e)
    elif zoxide_entry:
        try:
            launch_or_attach_adhoc(zoxide_entry.path)
        except Exception as e:
            _report(f"Failed to launch adhoc session for {zoxide_entry.path}", e)
    elif session_to_switch:
        try:
            attach_session(session_to_switch)
        except Exception as e:
            _report(f"Failed to switch to session {session_to_switch}", e)


def run_dashboard() -> None:
    """Run the Kata dashboard."""
    app = KataDashboard()
    app.run()
    launch_pending_target(app, interactive=False)
