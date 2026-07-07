"""Tree view widget for grouped projects."""

import json

from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Tree

from kata.core.config import KATA_CONFIG_DIR
from kata.core.models import Project, SessionStatus
from kata.services.registry import get_registry
from kata.services.sessions import get_all_session_statuses
from kata.tui.icons import project_type_icon, status_indicator
from kata.utils.colors import resolve_color
from kata.utils.detection import detect_project_type
from kata.utils.git import format_git_indicator_rich, get_git_status

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


def _collect_project_labels(
    projects: list[Project],
    all_statuses: dict[str, SessionStatus],
) -> dict[str, str]:
    """Compute labels for all projects (I/O-heavy, meant for a worker thread)."""
    labels: dict[str, str] = {}
    for project in projects:
        status = all_statuses.get(project.name, SessionStatus.IDLE)
        indicator = status_indicator(status)

        project_type = detect_project_type(project.path)
        type_icon = project_type_icon(project_type.value)
        git_status = get_git_status(project.path)
        git_indicator = format_git_indicator_rich(git_status)
        shortcut_prefix = f"[cyan][{project.shortcut}][/cyan] " if project.shortcut else ""
        project_color = resolve_color(getattr(project, "color", None))
        color_bar = f"[{project_color}]┃[/{project_color}] " if project_color else "  "
        if git_indicator:
            labels[project.name] = (
                f"{color_bar}{indicator} {shortcut_prefix}{type_icon} {project.name} [dim]{git_indicator}[/dim]"
            )
        else:
            labels[project.name] = (
                f"{color_bar}{indicator} {shortcut_prefix}{type_icon} {project.name}"
            )
    return labels


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
        padding: 1 2;
        scrollbar-size: 1 1;
    }

    ProjectTree > Tree:focus {
        border: none;
    }

    ProjectTree > Tree > .tree--guides {
        color: $surface-lighten-2;
    }

    ProjectTree > Tree > .tree--cursor {
        background: $primary 22%;
    }

    ProjectTree > Tree > .tree--highlight {
        background: $primary 22%;
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
        """Build initial tree structure without I/O-heavy operations.

        Skips git status and project type detection for fast first paint.
        These are populated by the first refresh_projects() call.
        """
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

        # Sort groups and projects - use IDLE status and generic icon initially
        self._projects_by_name.clear()
        for group_name in sorted(groups.keys()):
            group_key = group_name.lower()
            group_icon = GROUP_ICONS.get(group_key, GROUP_ICONS["default"])
            group_label = f"[bold dim]{group_icon} {group_name.upper()}[/bold dim]"

            group_node = tree.root.add(group_label, expand=group_name in self._expanded_groups)
            group_node.data = {"type": "group", "name": group_name}

            for project in sorted(groups[group_name], key=lambda p: p.name):
                indicator = status_indicator(SessionStatus.IDLE)
                shortcut_prefix = f"[cyan][{project.shortcut}][/cyan] " if project.shortcut else ""
                project_color = resolve_color(getattr(project, "color", None))
                color_bar = f"[{project_color}]┃[/{project_color}] " if project_color else "  "
                label = f"{color_bar}{indicator} {shortcut_prefix}{project.name}"

                project_node = group_node.add_leaf(label)
                project_node.data = {
                    "type": "project",
                    "project": project,
                    "label_markup": label,
                }
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
                            # Also directly update preview for instant first paint
                            try:
                                from kata.tui.widgets.preview import PreviewPane

                                preview = self.app.query_one(PreviewPane)
                                preview.show_project_quick(project)
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
        except (OSError, json.JSONDecodeError):
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
        except OSError:
            pass

    def refresh_projects(self) -> None:
        """Kick off a background refresh — I/O runs in a worker thread."""

        def _work() -> None:
            result = self._compute_refresh()
            if result is not None:
                self.app.call_from_thread(self._apply_refresh, *result)

        self.run_worker(_work, thread=True, exclusive=True, group="refresh")

    def _compute_refresh(self) -> tuple[list[Project], dict[str, str], set[str]] | None:
        """Heavy I/O: reload registry, fetch statuses, compute labels (runs in thread)."""
        try:
            registry = get_registry()
            registry.reload()
            projects = registry.list_all()
            all_statuses = get_all_session_statuses()
            labels = _collect_project_labels(projects, all_statuses)
            current_names = {p.name for p in projects}
            return projects, labels, current_names
        except Exception:
            return None

    def _apply_refresh(
        self,
        projects: list[Project],
        labels: dict[str, str],
        current_names: set[str],
    ) -> None:
        """Apply computed labels to the tree (runs on main thread, no I/O)."""
        tree = self.query_one("#project-tree", Tree)
        existing_names = set(self._projects_by_name.keys())

        # Check if any project changed group (move to group)
        groups_changed = False
        for p in projects:
            old = self._projects_by_name.get(p.name)
            if old and old.group != p.group:
                groups_changed = True
                break

        if current_names == existing_names and tree.root.children and not groups_changed:
            # Fast path: same projects, same groups — update labels in-place (cursor preserved)
            for group_node in tree.root.children:
                if not (group_node.data and group_node.data.get("type") == "group"):
                    continue
                for project_node in group_node.children:
                    if not (project_node.data and project_node.data.get("type") == "project"):
                        continue
                    project = project_node.data["project"]
                    new_label = labels.get(project.name, "")
                    # Compare against the stored markup string, not str(label):
                    # str() renders the Content and drops the markup, so it never
                    # equals new_label and every label was needlessly rewritten.
                    old_markup = project_node.data.get("label_markup")
                    if new_label and old_markup != new_label:
                        project_node.set_label(new_label)
                        project_node.data["label_markup"] = new_label
            return

        # Slow path: project set changed — full rebuild
        for node in tree.root.children:
            if node.data and node.data.get("type") == "group":
                group_name = node.data.get("name")
                if node.is_expanded:
                    self._expanded_groups.add(group_name)
                else:
                    self._expanded_groups.discard(group_name)

        tree.clear()

        groups: dict[str, list[Project]] = {}
        for project in projects:
            group_name = project.group or "Uncategorized"
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(project)

        self._projects_by_name.clear()
        for group_name in sorted(groups.keys()):
            group_key = group_name.lower()
            group_icon = GROUP_ICONS.get(group_key, GROUP_ICONS["default"])
            group_label = f"[bold dim]{group_icon} {group_name.upper()}[/bold dim]"

            group_node = tree.root.add(group_label, expand=group_name in self._expanded_groups)
            group_node.data = {"type": "group", "name": group_name}

            for project in sorted(groups[group_name], key=lambda p: p.name):
                label = labels.get(project.name, project.name)

                project_node = group_node.add_leaf(label)
                project_node.data = {
                    "type": "project",
                    "project": project,
                    "label_markup": label,
                }
                self._projects_by_name[project.name] = project

        tree.root.expand()

    def get_selected_project(self) -> Project | None:
        """Get the currently selected project."""
        tree = self.query_one("#project-tree", Tree)
        node = tree.cursor_node
        if node and node.data and node.data.get("type") == "project":
            return node.data.get("project")
        return None

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle node selection (Enter key)."""
        node = event.node
        if node.data:
            if node.data.get("type") == "project":
                project = node.data.get("project")
                if project:
                    self.post_message(self.ProjectSelected(project))
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
        """Handle node highlight (cursor movement).

        Posts ProjectHighlighted; the app's handler updates the preview. We do
        NOT also update the preview directly here — doing both triggered the
        async preview load twice per cursor move.
        """
        node = event.node
        if node and node.data and node.data.get("type") == "project":
            project = node.data.get("project")
            if project:
                self.post_message(self.ProjectHighlighted(project))
