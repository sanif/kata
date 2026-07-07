"""Preview pane widget for displaying project details."""

import os
from datetime import datetime

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from kata.core.models import Project
from kata.core.templates import get_template_path
from kata.services.sessions import get_session_status
from kata.tui.icons import project_type_icon
from kata.tui.widgets.layout import parse_tmuxp_config, render_layout_summary
from kata.utils.colors import resolve_color
from kata.utils.detection import detect_project_type
from kata.utils.git import get_git_status
from kata.utils.paths import sanitize_session_name
from kata.utils.zoxide import ZoxideEntry


def _compute_project_preview(project: Project) -> dict:
    """Compute all I/O-heavy preview data in a thread."""
    status = get_session_status(sanitize_session_name(project.name))
    project_type = detect_project_type(project.path)
    git_status = get_git_status(project.path)
    config_path = get_template_path(project)
    layout = parse_tmuxp_config(config_path)
    return {
        "status": status,
        "project_type": project_type,
        "git_status": git_status,
        "layout": layout,
    }


def _compute_zoxide_preview(entry: ZoxideEntry) -> dict:
    """Compute I/O-heavy preview data for a zoxide entry in a thread."""
    project_type = detect_project_type(entry.path)
    git_status = get_git_status(entry.path)
    return {
        "project_type": project_type,
        "git_status": git_status,
    }


class PreviewPane(Widget):
    """Preview pane showing project details and stats."""

    DEFAULT_CSS = """
    PreviewPane {
        width: 100%;
        height: 100%;
        background: $background;
    }

    PreviewPane #preview-content {
        width: 100%;
        height: 100%;
        color: $text;
    }

    PreviewPane.-empty {
        content-align: center middle;
    }

    PreviewPane.-empty #preview-content {
        text-align: center;
        color: $text-muted;
    }
    """

    project: reactive[Project | None] = reactive(None)

    def __init__(
        self,
        project: Project | None = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.project = project
        self._current_project_name: str | None = None

    def compose(self):
        """Compose the widget."""
        yield Static(id="preview-content")

    def on_mount(self) -> None:
        """Update content on mount."""
        self._show_empty()

    def _show_empty(self) -> None:
        """Show the empty state."""
        try:
            content_widget = self.query_one("#preview-content", Static)
        except Exception:
            return
        self.add_class("-empty")
        content_widget.update(
            "[dim]Select a project to view details[/dim]\n\n"
            "[$primary]↑↓[/$primary] [dim]navigate[/dim]   "
            "[$primary]enter[/$primary] [dim]launch[/dim]   "
            "[$primary]/[/$primary] [dim]search[/dim]"
        )

    def show_project_quick(self, project: Project) -> None:
        """Show project with minimal info instantly (no I/O), then load details async."""
        self.project = project
        self._current_project_name = project.name
        self.remove_class("-empty")

        try:
            content_widget = self.query_one("#preview-content", Static)
        except Exception:
            return

        home = os.path.expanduser("~")
        display_path = project.path
        if display_path.startswith(home):
            display_path = "~" + display_path[len(home) :]

        last_opened = self._format_date(project.last_opened) if project.last_opened else "Never"
        sparkline = self._generate_sparkline(project.times_opened)

        # Instant content with no I/O
        content = f"  [bold]󰉋[/bold]  [bold]{project.name}[/bold]   [dim]○ ...[/dim]"
        content += f"\n  [dim]{display_path}[/dim]"
        content += "\n\n  [dim]╶───────────────────────────────╴[/dim]"
        content += f"\n\n  [dim]group[/dim]        {project.group.lower()}"
        # Color swatch
        project_color = resolve_color(getattr(project, "color", None))
        if project_color:
            content += f"\n  [dim]color[/dim]        [{project_color}]██[/{project_color}]  {project.color}"
        content += "\n\n  [dim]╶───────────────────────────────╴[/dim]"
        content += f"\n\n  [dim]activity[/dim]     {sparkline}"
        content += f"\n  [dim]opened[/dim]       {project.times_opened}×"
        content += f"\n  [dim]last[/dim]         {last_opened}"

        content_widget.update(content)

        # Kick off async full load
        self._load_project_details(project)

    def _load_project_details(self, project: Project) -> None:
        """Load full project details in a background thread."""

        def _work() -> None:
            data = _compute_project_preview(project)
            # Schedule UI update back on the main thread
            self.app.call_from_thread(self._apply_project_result, project.name, project, data)

        self.run_worker(_work, thread=True, exclusive=True, group="preview")

    def _apply_project_result(self, expected_name: str, project: Project, data: dict) -> None:
        """Apply computed project data if still relevant."""
        if self._current_project_name != expected_name:
            return
        self._render_full_project(project, data)

    def _render_full_project(self, project: Project, data: dict) -> None:
        """Render full project preview with computed data (no I/O)."""
        try:
            content_widget = self.query_one("#preview-content", Static)
        except Exception:
            return

        status = data["status"]
        project_type = data["project_type"]
        git_status = data["git_status"]
        layout = data["layout"]

        last_opened = self._format_date(project.last_opened) if project.last_opened else "Never"

        type_icon = project_type_icon(project_type.value)

        status_styles = {
            "active": ("$success", "●", "running"),
            "detached": ("$warning", "●", "paused"),
            "idle": ("dim", "○", "idle"),
        }
        status_color, status_icon, status_text = status_styles.get(
            status.value, ("dim", "○", "idle")
        )

        home = os.path.expanduser("~")
        display_path = project.path
        if display_path.startswith(home):
            display_path = "~" + display_path[len(home) :]

        content = f"  [bold]{type_icon}[/bold]  [bold]{project.name}[/bold]   [{status_color}]{status_icon} {status_text}[/{status_color}]"
        content += f"\n  [dim]{display_path}[/dim]"
        content += "\n\n  [dim]╶───────────────────────────────╴[/dim]"
        content += f"\n\n  [dim]group[/dim]        {project.group.lower()}"
        content += f"\n  [dim]type[/dim]         {project_type.value}"
        # Color swatch
        project_color = resolve_color(getattr(project, "color", None))
        if project_color:
            content += f"\n  [dim]color[/dim]        [{project_color}]██[/{project_color}]  {project.color}"

        if git_status.is_git_repo:
            branch_display = git_status.branch or "unknown"
            dirty = " [$warning]✱[/$warning]" if git_status.is_dirty else ""
            sync_info = ""
            if git_status.ahead > 0:
                sync_info += f" [$success]↑{git_status.ahead}[/$success]"
            if git_status.behind > 0:
                sync_info += f" [$error]↓{git_status.behind}[/$error]"
            content += f"\n  [dim]branch[/dim]       [$primary]{branch_display}[/$primary]{dirty}{sync_info}"

        content += "\n\n  [dim]╶───────────────────────────────╴[/dim]"

        sparkline = self._generate_sparkline(project.times_opened)
        content += f"\n\n  [dim]activity[/dim]     {sparkline}"
        content += f"\n  [dim]opened[/dim]       {project.times_opened}×"
        content += f"\n  [dim]last[/dim]         {last_opened}"

        if layout:
            layout_summary = render_layout_summary(layout)
            content += "\n\n  [dim]╶───────────────────────────────╴[/dim]"
            content += f"\n\n  [dim]layout[/dim]       {layout_summary}"

        content_widget.update(content)

    def update_project(self, project: Project | None) -> None:
        """Update the displayed project — instant then async."""
        if project is None:
            self.project = None
            self._current_project_name = None
            self._show_empty()
            return
        self.show_project_quick(project)

    def refresh_status(self) -> None:
        """Refresh status for current project (async)."""
        if self.project:
            self._load_project_details(self.project)

    def update_zoxide(self, entry: ZoxideEntry) -> None:
        """Update to show a zoxide entry — instant then async."""
        self.project = None
        self._current_project_name = None
        self.remove_class("-empty")

        try:
            content_widget = self.query_one("#preview-content", Static)
        except Exception:
            return

        home = os.path.expanduser("~")
        display_path = entry.path
        if display_path.startswith(home):
            display_path = "~" + display_path[len(home) :]

        # Instant content
        content = f"  [bold][$secondary]󰉋[/$secondary][/bold]  [bold]{entry.name}[/bold]   [dim]○ not registered[/dim]"
        content += f"\n  [dim]{display_path}[/dim]"
        content += "\n\n  [dim]╶───────────────────────────────╴[/dim]"
        content += f"\n\n  [dim]score[/dim]        {entry.score:.1f}"
        content += "\n\n  [dim]Press[/dim] [bold]a[/bold] [dim]to add as project[/dim]"

        content_widget.update(content)

        # Load git/type details async
        self._current_project_name = f"__zoxide__{entry.path}"

        def _work() -> None:
            data = _compute_zoxide_preview(entry)
            expected_key = f"__zoxide__{entry.path}"
            self.app.call_from_thread(self._apply_zoxide_result, expected_key, entry, data)

        self.run_worker(_work, thread=True, exclusive=True, group="preview")

    def _apply_zoxide_result(self, expected_key: str, entry: ZoxideEntry, data: dict) -> None:
        """Apply computed zoxide data if still relevant."""
        if self._current_project_name != expected_key:
            return
        self._render_full_zoxide(entry, data)

    def _render_full_zoxide(self, entry: ZoxideEntry, data: dict) -> None:
        """Render full zoxide preview."""
        try:
            content_widget = self.query_one("#preview-content", Static)
        except Exception:
            return

        project_type = data["project_type"]
        git_status = data["git_status"]

        home = os.path.expanduser("~")
        display_path = entry.path
        if display_path.startswith(home):
            display_path = "~" + display_path[len(home) :]

        content = f"  [bold][$secondary]󰉋[/$secondary][/bold]  [bold]{entry.name}[/bold]   [dim]○ not registered[/dim]"
        content += f"\n  [dim]{display_path}[/dim]"
        content += "\n\n  [dim]╶───────────────────────────────╴[/dim]"
        content += f"\n\n  [dim]type[/dim]         {project_type.value}"

        if git_status.is_git_repo:
            branch_display = git_status.branch or "unknown"
            dirty = " [$warning]✱[/$warning]" if git_status.is_dirty else ""
            sync_info = ""
            if git_status.ahead > 0:
                sync_info += f" [$success]↑{git_status.ahead}[/$success]"
            if git_status.behind > 0:
                sync_info += f" [$error]↓{git_status.behind}[/$error]"
            content += f"\n  [dim]branch[/dim]       [$primary]{branch_display}[/$primary]{dirty}{sync_info}"

        content += "\n\n  [dim]╶───────────────────────────────╴[/dim]"
        content += f"\n\n  [dim]score[/dim]        {entry.score:.1f}"
        content += "\n\n  [dim]Press[/dim] [bold]a[/bold] [dim]to add as project[/dim]"

        content_widget.update(content)

    def _generate_sparkline(self, count: int, width: int = 12) -> str:
        """Generate a sparkline bar showing activity level.

        The fill colour steps through real tiers by open count: none, low,
        medium, high, very high — each a distinct colour.
        """
        max_count = 50
        filled = min(count, max_count) * width // max_count
        filled_blocks = "▓" * filled
        empty_blocks = "░" * (width - filled)
        empty = f"[dim]{empty_blocks}[/dim]"

        if count == 0:
            return f"[dim]{filled_blocks}{empty_blocks}[/dim]"
        elif count < 5:
            color = "dim"  # low
        elif count < 15:
            color = "$secondary"  # medium
        elif count < 30:
            color = "$primary"  # high
        else:
            color = "$success"  # very high
        return f"[{color}]{filled_blocks}[/{color}]{empty}"

    def _format_date(self, date_val: str | datetime | None) -> str:
        """Format a date string or datetime for display."""
        if not date_val:
            return "Unknown"

        try:
            if isinstance(date_val, datetime):
                dt = date_val
            else:
                dt = datetime.fromisoformat(str(date_val))

            now = datetime.now()
            diff = now - dt

            if diff.days == 0:
                hours = diff.seconds // 3600
                if hours == 0:
                    minutes = diff.seconds // 60
                    if minutes == 0:
                        return "Just now"
                    return f"{minutes}m ago"
                return f"{hours}h ago"
            elif diff.days == 1:
                return "Yesterday"
            elif diff.days < 7:
                return f"{diff.days} days ago"
            else:
                return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return str(date_val) if date_val else "Unknown"
