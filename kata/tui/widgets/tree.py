"""Tree view widget for grouped projects."""

import json

from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from kata.core.config import KATA_CONFIG_DIR
from kata.core.models import Project, SessionStatus
from kata.services.registry import get_registry
from kata.services.sessions import get_all_session_statuses, get_session_status
from kata.utils.detection import detect_project_type
from kata.utils.git import format_git_indicator_rich, get_git_status
from kata.utils.zoxide import ZoxideEntry

# Project type icons (Nerd Font)
PROJECT_TYPE_ICONS = {
    "python": "󰌠",
    "node": "󰎙",
    "rust": "󱘗",
    "go": "󰟓",
    "ruby": "󰴭",
    "generic": "󰉋",
}

# Group icons
GROUP_ICONS = {
    "dev": "󰛓",
    "work": "󰢱",
    "personal": "󰋑",
    "archive": "󰀼",
    "default": "󰉋",
}

# File to persist expanded state
TREE_STATE_FILE = KATA_CONFIG_DIR / "tree_state.json"


class ProjectTree(Widget):
    """Tree view for displaying projects grouped by category."""

    DEFAULT_CSS = """
    ProjectTree {
        width: 100%;
        height: 100%;
        background: $background;
    }

    ProjectTree > Tree {
        background: $background;
        padding: 1 1;
        scrollbar-size: 1 1;
    }

    ProjectTree > Tree:focus {
        border: none;
    }

    ProjectTree > Tree > .tree--guides {
        color: $text-muted;
    }

    ProjectTree > Tree > .tree--cursor {
        background: $surface;
    }

    ProjectTree > Tree > .tree--highlight {
        background: $surface;
    }
    """

    class ProjectSelected(Message, bubble=True):
        """Message sent when a project is selected."""

        def __init__(self, project: Project) -> None:
            super().__init__()
            self.project = project

    class ProjectHighlighted(Message, bubble=True):
        """Message sent when a project is highlighted (cursor moved)."""

        def __init__(self, project: Project) -> None:
            super().__init__()
            self.project = project

    class ZoxideSelected(Message, bubble=True):
        """Message sent when a zoxide entry is selected."""

        def __init__(self, entry: ZoxideEntry) -> None:
            super().__init__()
            self.entry = entry

    class ZoxideHighlighted(Message, bubble=True):
        """Message sent when a zoxide entry is highlighted."""

        def __init__(self, entry: ZoxideEntry) -> None:
            super().__init__()
            self.entry = entry

    # Track expanded groups
    _expanded_groups: reactive[set[str]] = reactive(set, init=False)

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the project tree."""
        super().__init__(name=name, id=id, classes=classes)
        self._projects_by_name: dict[str, Project] = {}
        self._load_expanded_state()

    def compose(self):
        """Compose the widget."""
        yield Tree("Projects", id="project-tree")

    def on_mount(self) -> None:
        """Set up the tree when mounted."""
        # Initial build without status (faster startup)
        self._build_tree_initial()
        # Auto-highlight first project after a brief delay
        self.call_later(self._highlight_first_project)
        # Focus the tree for keyboard navigation
        self.call_later(self._focus_tree)

    def _build_tree_initial(self) -> None:
        """Build initial tree structure (status will be updated separately)."""
        tree = self.query_one("#project-tree", Tree)
        tree.clear()

        registry = get_registry()
        projects = registry.list_all()

        # Group projects by group name
        groups: dict[str, list[Project]] = {}
        for project in projects:
            group_name = project.group or "Uncategorized"
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(project)

        # Sort groups and projects - use IDLE status initially
        self._projects_by_name.clear()
        for group_name in sorted(groups.keys()):
            group_key = group_name.lower()
            group_icon = GROUP_ICONS.get(group_key, GROUP_ICONS["default"])
            group_label = f"[dim]{group_icon} {group_name.lower()}[/dim]"

            group_node = tree.root.add(group_label, expand=group_name in self._expanded_groups)
            group_node.data = {"type": "group", "name": group_name}

            for project in sorted(groups[group_name], key=lambda p: p.name):
                # Use IDLE status initially - will be updated by refresh
                indicator = self._get_status_indicator(SessionStatus.IDLE)

                project_type = detect_project_type(project.path)
                type_icon = PROJECT_TYPE_ICONS.get(project_type.value, PROJECT_TYPE_ICONS["generic"])

                git_status = get_git_status(project.path)
                git_indicator = format_git_indicator_rich(git_status)

                # Shortcut prefix if assigned
                shortcut_prefix = f"[cyan][{project.shortcut}][/cyan] " if project.shortcut else ""

                if git_indicator:
                    label = f"{indicator} {shortcut_prefix}{type_icon} {project.name} [dim]{git_indicator}[/dim]"
                else:
                    label = f"{indicator} {shortcut_prefix}{type_icon} {project.name}"

                project_node = group_node.add_leaf(label)
                project_node.data = {"type": "project", "project": project}
                self._projects_by_name[project.name] = project

        tree.root.expand()

    def _focus_tree(self) -> None:
        """Focus the inner tree widget."""
        try:
            tree = self.query_one("#project-tree", Tree)
            tree.focus()
        except Exception:
            pass

    def _highlight_first_project(self) -> None:
        """Highlight the first project in the tree (cursor only, no selection)."""
        try:
            tree = self.query_one("#project-tree", Tree)
            # Find first project node and move cursor to it
            for group_node in tree.root.children:
                if not group_node.is_expanded:
                    group_node.expand()
                for project_node in group_node.children:
                    if project_node.data and project_node.data.get("type") == "project":
                        # Move cursor without selecting (which would launch)
                        tree.move_cursor(project_node)
                        project = project_node.data.get("project")
                        if project:
                            self.post_message(self.ProjectHighlighted(project))
                            # Also directly update preview
                            try:
                                from kata.tui.widgets.preview import PreviewPane

                                preview = self.app.query_one(PreviewPane)
                                preview.update_project(project)
                            except Exception:
                                pass
                        return
        except Exception:
            pass

    def _load_expanded_state(self) -> None:
        """Load expanded group state from disk."""
        try:
            if TREE_STATE_FILE.exists():
                data = json.loads(TREE_STATE_FILE.read_text(encoding="utf-8"))
                self._expanded_groups = set(data.get("expanded_groups", []))
            else:
                self._expanded_groups = set()
        except (json.JSONDecodeError, IOError):
            self._expanded_groups = set()

    def _save_expanded_state(self) -> None:
        """Save expanded group state to disk."""
        try:
            TREE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {"expanded_groups": list(self._expanded_groups)}
            TREE_STATE_FILE.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        except IOError:
            pass

    def _get_status_indicator(self, status: SessionStatus) -> str:
        """Get the status indicator for a session status."""
        indicators = {
            SessionStatus.ACTIVE: "[green]◆[/green]",
            SessionStatus.DETACHED: "[yellow]◆[/yellow]",
            SessionStatus.IDLE: "[dim]◇[/dim]",
        }
        return indicators.get(status, "[dim]◇[/dim]")

    def refresh_projects(self) -> None:
        """Refresh the project tree from registry."""
        tree = self.query_one("#project-tree", Tree)

        # Capture current expanded state before clearing
        for node in tree.root.children:
            if node.data and node.data.get("type") == "group":
                group_name = node.data.get("name")
                if node.is_expanded:
                    self._expanded_groups.add(group_name)
                else:
                    self._expanded_groups.discard(group_name)

        tree.clear()

        registry = get_registry()
        projects = registry.list_all()

        # Get all session statuses in one batch call (more efficient)
        all_statuses = get_all_session_statuses()

        # Group projects by group name
        groups: dict[str, list[Project]] = {}
        for project in projects:
            group_name = project.group or "Uncategorized"
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(project)

        # Sort groups and projects
        self._projects_by_name.clear()
        for group_name in sorted(groups.keys()):
            # Get group icon
            group_key = group_name.lower()
            group_icon = GROUP_ICONS.get(group_key, GROUP_ICONS["default"])
            group_label = f"[dim]{group_icon} {group_name.lower()}[/dim]"

            group_node = tree.root.add(group_label, expand=group_name in self._expanded_groups)
            group_node.data = {"type": "group", "name": group_name}

            for project in sorted(groups[group_name], key=lambda p: p.name):
                # Use batched status, fall back to IDLE if not found
                status = all_statuses.get(project.name, SessionStatus.IDLE)
                indicator = self._get_status_indicator(status)

                # Get project type icon
                project_type = detect_project_type(project.path)
                type_icon = PROJECT_TYPE_ICONS.get(project_type.value, PROJECT_TYPE_ICONS["generic"])

                # Get git status for the project
                git_status = get_git_status(project.path)
                git_indicator = format_git_indicator_rich(git_status)

                # Shortcut prefix if assigned
                shortcut_prefix = f"[cyan][{project.shortcut}][/cyan] " if project.shortcut else ""

                if git_indicator:
                    label = f"{indicator} {shortcut_prefix}{type_icon} {project.name} [dim]{git_indicator}[/dim]"
                else:
                    label = f"{indicator} {shortcut_prefix}{type_icon} {project.name}"

                project_node = group_node.add_leaf(label)
                project_node.data = {"type": "project", "project": project}
                self._projects_by_name[project.name] = project

        tree.root.expand()

    def get_selected_project(self) -> Project | None:
        """Get the currently selected project."""
        tree = self.query_one("#project-tree", Tree)
        node = tree.cursor_node
        if node and node.data and node.data.get("type") == "project":
            return node.data.get("project")
        return None

    def get_selected_zoxide(self) -> ZoxideEntry | None:
        """Get the currently selected zoxide entry."""
        tree = self.query_one("#project-tree", Tree)
        node = tree.cursor_node
        if node and node.data and node.data.get("type") == "zoxide":
            return node.data.get("entry")
        return None

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle node selection (Enter key)."""
        node = event.node
        if node.data:
            if node.data.get("type") == "project":
                project = node.data.get("project")
                if project:
                    self.post_message(self.ProjectSelected(project))
            elif node.data.get("type") == "zoxide":
                entry = node.data.get("entry")
                if entry:
                    self.post_message(self.ZoxideSelected(entry))
            elif node.data.get("type") == "group":
                # Toggle group expansion
                group_name = node.data.get("name")
                if node.is_expanded:
                    node.collapse()
                    self._expanded_groups.discard(group_name)
                else:
                    node.expand()
                    self._expanded_groups.add(group_name)
                self._save_expanded_state()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Handle node highlight (cursor movement)."""
        node = event.node
        if node and node.data:
            if node.data.get("type") == "project":
                project = node.data.get("project")
                if project:
                    self.post_message(self.ProjectHighlighted(project))
                    try:
                        from kata.tui.widgets.preview import PreviewPane
                        preview = self.app.query_one(PreviewPane)
                        preview.update_project(project)
                    except Exception:
                        pass
            elif node.data.get("type") == "zoxide":
                entry = node.data.get("entry")
                if entry:
                    self.post_message(self.ZoxideHighlighted(entry))
                    try:
                        from kata.tui.widgets.preview import PreviewPane
                        preview = self.app.query_one(PreviewPane)
                        preview.update_zoxide(entry)
                    except Exception:
                        pass

    def expand_all(self) -> None:
        """Expand all group nodes."""
        tree = self.query_one("#project-tree", Tree)
        for child in tree.root.children:
            if child.data and child.data.get("type") == "group":
                child.expand()
                self._expanded_groups.add(child.data.get("name", ""))
        self._save_expanded_state()

    def collapse_all(self) -> None:
        """Collapse all group nodes."""
        tree = self.query_one("#project-tree", Tree)
        for child in tree.root.children:
            if child.data and child.data.get("type") == "group":
                child.collapse()
        self._expanded_groups.clear()
        self._save_expanded_state()

    def filter_projects(self, query: str) -> None:
        """Filter projects by search query.

        Args:
            query: Search query to filter by (fuzzy match on name)
        """
        if not query:
            self.refresh_projects()
            return

        query_lower = query.lower()
        tree = self.query_one("#project-tree", Tree)
        tree.clear()

        registry = get_registry()
        projects = registry.list_all()

        # Get all session statuses in one batch call
        all_statuses = get_all_session_statuses()

        # Filter registered projects and group
        groups: dict[str, list[Project]] = {}
        for project in projects:
            if self._fuzzy_match(query_lower, project.name.lower()):
                group_name = project.group or "Uncategorized"
                if group_name not in groups:
                    groups[group_name] = []
                groups[group_name].append(project)

        # Build filtered tree
        for group_name in sorted(groups.keys()):
            group_key = group_name.lower()
            group_icon = GROUP_ICONS.get(group_key, GROUP_ICONS["default"])
            group_label = f"[dim]{group_icon} {group_name.lower()}[/dim]"

            group_node = tree.root.add(group_label, expand=True)
            group_node.data = {"type": "group", "name": group_name}

            for project in sorted(groups[group_name], key=lambda p: p.name):
                status = all_statuses.get(project.name, SessionStatus.IDLE)
                indicator = self._get_status_indicator(status)

                project_type = detect_project_type(project.path)
                type_icon = PROJECT_TYPE_ICONS.get(project_type.value, PROJECT_TYPE_ICONS["generic"])

                git_status = get_git_status(project.path)
                git_indicator = format_git_indicator_rich(git_status)

                # Shortcut prefix if assigned
                shortcut_prefix = f"[cyan][{project.shortcut}][/cyan] " if project.shortcut else ""

                if git_indicator:
                    label = f"{indicator} {shortcut_prefix}{type_icon} {project.name} [dim]{git_indicator}[/dim]"
                else:
                    label = f"{indicator} {shortcut_prefix}{type_icon} {project.name}"

                project_node = group_node.add_leaf(label)
                project_node.data = {"type": "project", "project": project}

        tree.root.expand()

    def _fuzzy_match(self, query: str, target: str) -> bool:
        """Check if query fuzzy matches target.

        Args:
            query: Search query
            target: String to match against

        Returns:
            True if all query characters appear in order in target
        """
        if not query:
            return True

        query_idx = 0
        for char in target:
            if query_idx < len(query) and char == query[query_idx]:
                query_idx += 1
        return query_idx == len(query)
