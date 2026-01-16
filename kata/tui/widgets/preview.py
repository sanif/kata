"""Preview pane widget for displaying project details."""

from datetime import datetime

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from kata.core.models import Project, SessionStatus
from kata.core.templates import get_template_path
from kata.services.sessions import get_session_status
from kata.utils.detection import detect_project_type
from kata.utils.git import get_git_status
from kata.utils.zoxide import ZoxideEntry
from kata.tui.widgets.layout import parse_tmuxp_config, render_layout_summary


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
        """Initialize the preview pane.

        Args:
            project: Initial project to display
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.project = project

    def compose(self):
        """Compose the widget."""
        yield Static(id="preview-content")

    def on_mount(self) -> None:
        """Update content on mount."""
        self._update_content()

    def watch_project(self, project: Project | None) -> None:
        """React to project changes."""
        # Only update if widget is mounted
        if self.is_mounted:
            self._update_content()

    def _update_content(self) -> None:
        """Update the preview content."""
        try:
            content_widget = self.query_one("#preview-content", Static)
        except Exception:
            # Widget not yet mounted
            return

        if self.project is None:
            self.add_class("-empty")
            content_widget.update("[dim]Select a project to view details[/dim]")
            return

        self.remove_class("-empty")
        project = self.project

        # Get status and type
        status = get_session_status(project.name)
        project_type = detect_project_type(project.path)

        # Get git status
        git_status = get_git_status(project.path)

        # Format dates
        created = self._format_date(project.created_at)
        last_opened = self._format_date(project.last_opened) if project.last_opened else "Never"

        # Project type icons
        type_icons = {
            "python": "󰌠",
            "node": "󰎙",
            "rust": "󱘗",
            "go": "󰟓",
            "ruby": "󰴭",
            "generic": "󰉋",
        }
        type_icon = type_icons.get(project_type.value, "󰉋")

        # Status styling
        status_styles = {
            "active": ("green", "◆", "running"),
            "detached": ("yellow", "◆", "paused"),
            "idle": ("dim", "◇", "idle"),
        }
        status_color, status_icon, status_text = status_styles.get(
            status.value, ("dim", "◇", "idle")
        )

        # Build header with icon
        content = f"""[bold]{type_icon} {project.name}[/bold]

[{status_color}]{status_icon} {status_text}[/{status_color}]
"""

        # Info section with aligned labels
        content += f"""
[dim]├─[/dim] [dim]group[/dim]   {project.group.lower()}
[dim]├─[/dim] [dim]type[/dim]    {project_type.value}"""

        # Add git info if available
        if git_status.is_git_repo:
            branch_display = git_status.branch or "unknown"
            dirty = " [yellow]✱[/yellow]" if git_status.is_dirty else ""
            sync_info = ""
            if git_status.ahead > 0:
                sync_info += f" [green]↑{git_status.ahead}[/green]"
            if git_status.behind > 0:
                sync_info += f" [red]↓{git_status.behind}[/red]"

            content += f"\n[dim]├─[/dim] [dim]branch[/dim]  [cyan]{branch_display}[/cyan]{dirty}{sync_info}"

        content += f"\n[dim]└─[/dim] [dim]path[/dim]    [dim]{project.path}[/dim]"

        # Activity sparkline (visual representation of usage)
        sparkline = self._generate_sparkline(project.times_opened)

        # Stats section
        content += f"""

[dim]─────────────────────────────[/dim]

  [dim]activity[/dim]  {sparkline}
  [dim]opened[/dim]    {project.times_opened}×
  [dim]last[/dim]      {last_opened}"""

        # Add layout summary
        config_path = get_template_path(project)
        layout = parse_tmuxp_config(config_path)
        if layout:
            layout_summary = render_layout_summary(layout)
            content += f"""

[dim]─────────────────────────────[/dim]

[dim]{layout_summary}[/dim]"""

        content_widget.update(content)

    def _generate_sparkline(self, count: int, width: int = 10) -> str:
        """Generate a sparkline bar showing activity level.

        Args:
            count: Number of times opened
            width: Width of the sparkline in characters

        Returns:
            A colorized sparkline string
        """
        # Normalize count to a 0-width scale (cap at 50 opens for full bar)
        max_count = 50
        filled = min(count, max_count) * width // max_count

        # Use block characters for the bar
        blocks = "█" * filled + "░" * (width - filled)

        # Color based on activity level
        if count == 0:
            return f"[dim]{blocks}[/dim]"
        elif count < 5:
            return f"[dim]{blocks}[/dim]"
        elif count < 15:
            return f"[cyan]{blocks}[/cyan]"
        elif count < 30:
            return f"[green]{blocks}[/green]"
        else:
            return f"[yellow]{blocks}[/yellow]"

    def _get_status_indicator(self, status: SessionStatus) -> str:
        """Get the status indicator for a session status."""
        indicators = {
            SessionStatus.ACTIVE: "[green]◆[/green]",
            SessionStatus.DETACHED: "[yellow]◆[/yellow]",
            SessionStatus.IDLE: "[dim]◇[/dim]",
        }
        return indicators.get(status, "[dim]◇[/dim]")

    def _format_date(self, date_val: str | datetime | None) -> str:
        """Format a date string or datetime for display."""
        if not date_val:
            return "Unknown"

        try:
            # Handle both string and datetime objects
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

    def update_project(self, project: Project | None) -> None:
        """Update the displayed project.

        Args:
            project: Project to display, or None to show empty state
        """
        self.project = project
        # Force immediate update
        self._update_content()

    def refresh_status(self) -> None:
        """Refresh the status display for current project."""
        self._update_content()

    def update_zoxide(self, entry: ZoxideEntry) -> None:
        """Update to show a zoxide entry.

        Args:
            entry: Zoxide entry to display
        """
        self.project = None  # Clear project
        self.remove_class("-empty")

        try:
            content_widget = self.query_one("#preview-content", Static)
        except Exception:
            return

        # Get project type for the directory
        project_type = detect_project_type(entry.path)

        # Get git status
        git_status = get_git_status(entry.path)

        # Project type icons
        type_icons = {
            "python": "󰌠",
            "node": "󰎙",
            "rust": "󱘗",
            "go": "󰟓",
            "ruby": "󰴭",
            "generic": "󰉋",
        }
        type_icon = type_icons.get(project_type.value, "󰉋")

        # Build content
        content = f"""[bold][yellow]󰉋[/yellow] {entry.name}[/bold]

[dim]◇ not registered[/dim]
"""

        # Info section
        content += f"""
[dim]├─[/dim] [dim]type[/dim]    {project_type.value}"""

        # Add git info if available
        if git_status.is_git_repo:
            branch_display = git_status.branch or "unknown"
            dirty = " [yellow]✱[/yellow]" if git_status.is_dirty else ""
            sync_info = ""
            if git_status.ahead > 0:
                sync_info += f" [green]↑{git_status.ahead}[/green]"
            if git_status.behind > 0:
                sync_info += f" [red]↓{git_status.behind}[/red]"

            content += f"\n[dim]├─[/dim] [dim]branch[/dim]  [cyan]{branch_display}[/cyan]{dirty}{sync_info}"

        content += f"\n[dim]└─[/dim] [dim]path[/dim]    [dim]{entry.path}[/dim]"

        # Zoxide score
        content += f"""

[dim]─────────────────────────────[/dim]

  [dim]zoxide score[/dim]  {entry.score:.1f}

[dim]─────────────────────────────[/dim]

[dim]Press [/dim][bold]a[/bold][dim] to add as project[/dim]"""

        content_widget.update(content)
