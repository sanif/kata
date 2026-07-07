"""Mouse-first workspace screen — persistent per-project working view.

herdr-style: a full-screen (non-modal) screen where the user clicks around
instead of hopping through modals. Left sidebar (toggleable with the ☰ button
or Ctrl+B) holds three sections — Projects, Changes, Files — and the content
area renders markdown, syntax-highlighted text, or diffs (unified/split).

Everything clickable has a keyboard twin: Tab/Shift+Tab cycle the sections,
1/2/3/4 jump straight to them, Enter activates rows, ``s`` flips
unified/split, ``e`` opens $EDITOR, Esc/q closes. All filesystem/git/JSONL
work runs in worker threads.
"""

from __future__ import annotations

from pathlib import Path

from rich.table import Table
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import DirectoryTree, Markdown, OptionList, Static
from textual.widgets.option_list import Option

from kata.core.models import Project
from kata.services.registry import get_registry
from kata.tui.screens.diff_viewer import compute_diff_text, format_change_label
from kata.tui.screens.file_browser import FilteredDirectoryTree
from kata.tui.screens.file_viewer import (
    MARKDOWN_SUFFIXES,
    _open_in_editor,
    classify_markdown_link,
    lexer_for_path,
    open_url_in_browser,
    read_text_file,
    syntax_theme_for,
)
from kata.utils.claude_sessions import get_session_edited_files
from kata.utils.colors import resolve_color
from kata.utils.diff import KIND_ADD, KIND_CONTEXT, KIND_DEL, SplitRow, build_split_rows
from kata.utils.git import ChangedFile, collect_uncommitted_changes

# Split-view cell backgrounds per (kind, dark?) — plain colors, chosen to read
# on both Kata dark and light theme families.
_SPLIT_BG = {
    (KIND_DEL, True): "#3f1d1d",
    (KIND_DEL, False): "#fee2e2",
    (KIND_ADD, True): "#14321d",
    (KIND_ADD, False): "#dcfce7",
}

_SECTION_IDS = ("ws-projects", "ws-changes", "ws-tree", "ws-content")


def render_split_table(rows: list[SplitRow], *, dark: bool) -> Table:
    """Build a two-column Rich table for a split diff.

    One renderable keeps both sides inherently synced when scrolling. Long
    lines are truncated with an ellipsis per column (no horizontal scroll).
    """
    table = Table(
        box=None,
        show_header=False,
        show_edge=False,
        padding=(0, 0),
        expand=True,
        pad_edge=False,
    )
    table.add_column(width=5, justify="right", style="dim", no_wrap=True)  # left no
    table.add_column(ratio=1, no_wrap=True, overflow="ellipsis")  # left text
    table.add_column(width=3, justify="center", style="dim", no_wrap=True)  # gutter
    table.add_column(width=5, justify="right", style="dim", no_wrap=True)  # right no
    table.add_column(ratio=1, no_wrap=True, overflow="ellipsis")  # right text

    for row in rows:
        left_style = _SPLIT_BG.get((row.left_kind, dark), "")
        right_style = _SPLIT_BG.get((row.right_kind, dark), "")
        left_style = f"on {left_style}" if left_style else ""
        right_style = f"on {right_style}" if right_style else ""
        if row.left_kind == KIND_CONTEXT:
            left_style = ""
        if row.right_kind == KIND_CONTEXT:
            right_style = ""
        gutter = "│"
        table.add_row(
            Text(str(row.left_no) if row.left_no is not None else ""),
            Text(row.left_text, style=left_style),
            Text(gutter),
            Text(str(row.right_no) if row.right_no is not None else ""),
            Text(row.right_text, style=right_style),
        )
    return table


class WorkspaceScreen(Screen[None]):
    """Full-screen per-project workspace with sidebar + content area."""

    # Session-level preferences (class vars persist across screen instances
    # for the lifetime of the app process).
    _sidebar_visible_pref: bool = True
    _diff_mode_pref: str = "unified"  # "unified" | "split"

    CSS = """
    WorkspaceScreen {
        background: $background;
    }

    WorkspaceScreen #ws-header {
        width: 100%;
        height: 1;
        background: $panel;
    }

    WorkspaceScreen .ws-btn {
        width: auto;
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }

    WorkspaceScreen .ws-btn:hover {
        background: $primary 20%;
        color: $text;
    }

    WorkspaceScreen .ws-btn.-active {
        color: $primary;
        text-style: bold;
    }

    WorkspaceScreen #ws-title {
        width: 1fr;
        height: 1;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    WorkspaceScreen #ws-diff-toggle {
        width: auto;
        height: 1;
        display: none;
    }

    WorkspaceScreen #ws-body {
        width: 100%;
        height: 1fr;
    }

    WorkspaceScreen #ws-sidebar {
        width: 32;
        height: 100%;
        background: $surface;
        border-right: vkey $surface-lighten-1;
    }

    WorkspaceScreen .ws-section-title {
        width: 100%;
        height: 1;
        padding: 0 1;
        color: $text-muted;
        text-style: bold;
        background: $surface;
    }

    WorkspaceScreen #ws-projects {
        width: 100%;
        height: auto;
        max-height: 7;
        background: $surface;
        scrollbar-size: 1 1;
    }

    WorkspaceScreen #ws-changes {
        width: 100%;
        height: 30%;
        background: $surface;
        scrollbar-size: 1 1;
    }

    WorkspaceScreen #ws-tree-slot {
        width: 100%;
        height: 1fr;
    }

    WorkspaceScreen #ws-tree-slot DirectoryTree {
        width: 100%;
        height: 100%;
        background: $surface;
        scrollbar-size: 1 1;
    }

    WorkspaceScreen #ws-projects:focus,
    WorkspaceScreen #ws-changes:focus,
    WorkspaceScreen #ws-tree-slot DirectoryTree:focus {
        background: $primary 8%;
    }

    WorkspaceScreen #ws-projects > .option-list--option-highlighted,
    WorkspaceScreen #ws-changes > .option-list--option-highlighted {
        background: $primary 20%;
        color: $text;
    }

    WorkspaceScreen #ws-content {
        width: 1fr;
        height: 100%;
        background: $background;
        scrollbar-size: 1 1;
        padding: 0 1;
    }

    WorkspaceScreen #ws-content:focus {
        background: $primary 5%;
    }

    WorkspaceScreen #ws-text {
        width: auto;
        height: auto;
    }

    WorkspaceScreen #ws-md {
        width: 100%;
        height: auto;
        display: none;
    }

    WorkspaceScreen #ws-footer {
        width: 100%;
        height: 1;
        color: $text-muted;
        background: $panel;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=False),
        Binding("s", "toggle_diff_mode", "Split", show=False),
        Binding("e", "edit", "Editor", show=False),
        Binding("1", "focus_section('ws-projects')", "Projects", show=False),
        Binding("2", "focus_section('ws-changes')", "Changes", show=False),
        Binding("3", "focus_section('ws-tree')", "Files", show=False),
        Binding("4", "focus_section('ws-content')", "Content", show=False),
    ]

    def __init__(self, project: Project) -> None:
        super().__init__()
        self.project = project
        self.root = Path(project.path)
        self._projects: list[Project] = []
        self._changes: list[ChangedFile] = []
        self._claude_paths: set[Path] = set()
        self._diff_mode: str = type(self)._diff_mode_pref
        self._diff_text: str | None = None
        self._current_path: Path | None = None
        self._current_md_path: Path | None = None
        self._last_sidebar_focus: str = "ws-projects"
        self._load_gen = 0
        self._content_gen = 0

    # ── Layout ─────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Vertical(id="ws-root"):
            with Horizontal(id="ws-header"):
                yield Static("☰", id="ws-btn-sidebar", classes="ws-btn")
                yield Static(self._title_text(), id="ws-title")
                with Horizontal(id="ws-diff-toggle"):
                    yield Static("Unified", id="ws-btn-unified", classes="ws-btn")
                    yield Static("Split", id="ws-btn-split", classes="ws-btn")
                yield Static("✕", id="ws-btn-close", classes="ws-btn")
            with Horizontal(id="ws-body"):
                with Vertical(id="ws-sidebar"):
                    yield Static("󰀻 PROJECTS", classes="ws-section-title")
                    yield OptionList(id="ws-projects")
                    yield Static("󰊢 CHANGES", classes="ws-section-title")
                    yield OptionList(id="ws-changes")
                    yield Static("󰉋 FILES", classes="ws-section-title")
                    with Container(id="ws-tree-slot"):
                        yield FilteredDirectoryTree(str(self.root), id="ws-tree")
                with VerticalScroll(id="ws-content"):
                    yield Static("", id="ws-text")
                    yield Markdown(open_links=False, id="ws-md")
            yield Static(self._footer_text(), id="ws-footer")

    def _title_text(self) -> str:
        return f"󰆍 {self.project.name}"

    def _footer_text(self) -> str:
        return (
            "[dim]1/2/3/4[/dim] sections   "
            "[dim]tab[/dim] cycle   "
            "[dim]enter[/dim] open   "
            "[dim]ctrl+b[/dim] sidebar   "
            "[dim]s[/dim] unified/split   "
            "[dim]e[/dim] editor   "
            "[dim]esc/q[/dim] close"
        )

    def on_mount(self) -> None:
        self._show_empty()
        self._load_projects()
        self._load_changes()
        if type(self)._sidebar_visible_pref:
            self.action_focus_section("ws-projects")
        else:
            self._set_sidebar(False, move_focus=False)
            self.action_focus_section("ws-content")

    # ── Sidebar data (workers) ─────────────────────────────────

    def _load_projects(self) -> None:
        def _work() -> None:
            try:
                projects = get_registry().list_all()
            except Exception:
                projects = []
            self.app.call_from_thread(self._apply_projects, projects)

        self.run_worker(_work, thread=True, exclusive=True, group="ws_projects")

    def _apply_projects(self, projects: list[Project]) -> None:
        self._projects = projects
        try:
            option_list = self.query_one("#ws-projects", OptionList)
        except Exception:
            return
        option_list.clear_options()
        active_index = 0
        for i, project in enumerate(projects):
            color = resolve_color(getattr(project, "color", None))
            dot = f"[{color}]●[/{color}]" if color else "[dim]○[/dim]"
            name = project.name
            if len(name) > 24:
                name = name[:23] + "…"
            marker = " [cyan]◂[/cyan]" if project.path == self.project.path else ""
            option_list.add_option(Option(f"{dot} {name}{marker}"))
            if project.path == self.project.path:
                active_index = i
        if projects:
            option_list.highlighted = active_index

    def _load_changes(self) -> None:
        self._load_gen += 1
        gen = self._load_gen
        root = self.root

        def _work() -> None:
            changes = collect_uncommitted_changes(root)
            claude_paths: set[Path] = set()
            if changes:
                try:
                    claude_paths = get_session_edited_files(str(root))
                except Exception:
                    claude_paths = set()
            self.app.call_from_thread(self._apply_changes, gen, changes, claude_paths)

        self.run_worker(_work, thread=True, exclusive=True, group="ws_changes")

    def _apply_changes(
        self,
        gen: int,
        changes: list[ChangedFile] | None,
        claude_paths: set[Path],
    ) -> None:
        if gen != self._load_gen:
            return
        try:
            option_list = self.query_one("#ws-changes", OptionList)
        except Exception:
            return
        option_list.clear_options()

        if changes is None:
            self._changes = []
            self._claude_paths = set()
            option_list.add_option(Option("[dim]  not a git repository[/dim]", disabled=True))
            return
        if not changes:
            self._changes = []
            self._claude_paths = claude_paths
            option_list.add_option(Option("[dim]  working tree clean[/dim]", disabled=True))
            return

        self._changes = changes
        self._claude_paths = claude_paths
        for changed in changes:
            option_list.add_option(Option(format_change_label(changed, claude_paths, max_name=22)))
        option_list.highlighted = 0

    # ── Sidebar interactions ───────────────────────────────────

    @on(OptionList.OptionSelected, "#ws-projects")
    async def _on_project_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        if index is None or not (0 <= index < len(self._projects)):
            return
        await self._switch_project(self._projects[index])

    async def _switch_project(self, project: Project) -> None:
        if project.path == self.project.path:
            return
        self.project = project
        self.root = Path(project.path)
        try:
            self.query_one("#ws-title", Static).update(self._title_text())
        except Exception:
            pass
        # Rebuild the file tree for the new root. Awaited so the old tree (and
        # its id) is fully gone before the replacement mounts.
        try:
            slot = self.query_one("#ws-tree-slot", Container)
            await slot.remove_children()
            await slot.mount(FilteredDirectoryTree(str(self.root), id="ws-tree"))
        except Exception:
            pass
        self._show_empty()
        self._load_changes()
        self._apply_projects(self._projects)  # refresh the ◂ active marker

    @on(OptionList.OptionSelected, "#ws-changes")
    def _on_change_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        if index is None or not (0 <= index < len(self._changes)):
            return
        self._open_diff(self._changes[index])

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        event.stop()
        self._open_file(Path(event.path))

    # ── Content area ───────────────────────────────────────────

    def _show_empty(self) -> None:
        self._diff_text = None
        self._current_path = None
        self._current_md_path = None
        self._set_diff_toggle_visible(False)
        self._set_markdown_visible(False)
        try:
            self.query_one("#ws-text", Static).update(
                "[dim]Select a file or change from the sidebar[/dim]"
            )
        except Exception:
            pass

    def _set_markdown_visible(self, visible: bool) -> None:
        try:
            self.query_one("#ws-md", Markdown).display = visible
            self.query_one("#ws-text", Static).display = not visible
        except Exception:
            pass

    def _set_diff_toggle_visible(self, visible: bool) -> None:
        try:
            self.query_one("#ws-diff-toggle", Horizontal).display = visible
            if visible:
                self._update_diff_toggle_classes()
        except Exception:
            pass

    def _update_diff_toggle_classes(self) -> None:
        try:
            unified = self.query_one("#ws-btn-unified", Static)
            split = self.query_one("#ws-btn-split", Static)
            unified.set_class(self._diff_mode == "unified", "-active")
            split.set_class(self._diff_mode == "split", "-active")
        except Exception:
            pass

    def _open_file(self, path: Path) -> None:
        """Load a file's content into the content area (worker read)."""
        self._content_gen += 1
        gen = self._content_gen

        def _work() -> None:
            kind, payload = read_text_file(path)
            self.app.call_from_thread(self._apply_file, gen, path, kind, payload)

        self.run_worker(_work, thread=True, exclusive=True, group="ws_content")

    def _apply_file(self, gen: int, path: Path, kind: str, payload: str | None) -> None:
        if gen != self._content_gen:
            return
        self._diff_text = None
        self._current_path = path
        self._set_diff_toggle_visible(False)

        if kind == "binary":
            self._set_markdown_visible(False)
            self._set_text(
                "[yellow]󰈤 Binary file[/yellow]\n\n"
                "[dim]Press [/dim][dim]e[/dim][dim] to open it in your editor.[/dim]"
            )
            return
        if kind == "error":
            self._set_markdown_visible(False)
            self._set_text(f"[red]Failed to read file:[/red]\n[dim]{payload}[/dim]")
            return

        if path.suffix.lower() in MARKDOWN_SUFFIXES:
            self._current_md_path = path
            self._set_markdown_visible(True)
            try:
                md = self.query_one("#ws-md", Markdown)
                self.run_worker(md.update(payload or ""), exclusive=False)
            except Exception:
                pass
            self._scroll_content_top()
            return

        self._current_md_path = None
        self._set_markdown_visible(False)
        from rich.syntax import Syntax

        try:
            self._set_text(
                Syntax(
                    payload or "",
                    lexer_for_path(path),
                    line_numbers=True,
                    word_wrap=False,
                    theme=syntax_theme_for(self.app),
                    background_color="default",
                    indent_guides=False,
                )
            )
        except Exception:
            self._set_text(payload or "")
        self._scroll_content_top()

    def _open_diff(self, changed: ChangedFile) -> None:
        """Compute and render the diff for a changed file (worker)."""
        self._content_gen += 1
        gen = self._content_gen
        root = self.root

        def _work() -> None:
            text, note = compute_diff_text(root, changed)
            self.app.call_from_thread(self._apply_diff, gen, changed, text, note)

        self.run_worker(_work, thread=True, exclusive=True, group="ws_content")

    def _apply_diff(self, gen: int, changed: ChangedFile, text: str | None, note: str) -> None:
        if gen != self._content_gen:
            return
        self._current_path = changed.path
        self._current_md_path = None
        self._set_markdown_visible(False)

        if text is None:
            self._diff_text = None
            self._set_diff_toggle_visible(False)
            self._set_text(f"[dim]{note}[/dim]")
            return

        self._diff_text = text
        self._set_diff_toggle_visible(True)
        self._render_diff()

    def _render_diff(self) -> None:
        """Render the stored diff text in the current mode (no I/O)."""
        if self._diff_text is None:
            return
        dark = syntax_theme_for(self.app) == "ansi_dark"
        if self._diff_mode == "split":
            rows = build_split_rows(self._diff_text)
            if rows:
                self._set_text(render_split_table(rows, dark=dark))
            else:
                self._set_text("[dim]No hunks to display[/dim]")
        else:
            from rich.syntax import Syntax

            try:
                self._set_text(
                    Syntax(
                        self._diff_text,
                        "diff",
                        line_numbers=False,
                        word_wrap=False,
                        theme=syntax_theme_for(self.app),
                        background_color="default",
                    )
                )
            except Exception:
                self._set_text(self._diff_text)
        self._scroll_content_top()

    def _set_text(self, renderable) -> None:
        try:
            self.query_one("#ws-text", Static).update(renderable)
        except Exception:
            pass

    def _scroll_content_top(self) -> None:
        try:
            self.query_one("#ws-content", VerticalScroll).scroll_to(y=0, animate=False)
        except Exception:
            pass

    # ── Markdown links (same routing as MarkdownViewerScreen) ─

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        event.stop()
        current = self._current_md_path or self.root / "README.md"
        kind, resolved, anchor = classify_markdown_link(event.href or "", current, self.root)
        if kind == "external":
            open_url_in_browser(self, event.href)
        elif kind == "anchor":
            try:
                self.query_one("#ws-md", Markdown).goto_anchor(anchor)
            except Exception:
                pass
        elif kind == "outside":
            self.app.notify("Link points outside the project", severity="warning")
        elif kind == "missing":
            self.app.notify("Linked file not found", severity="warning")
        elif kind in ("markdown", "file"):
            self._open_file(resolved)

    # ── Header buttons (mouse) ─────────────────────────────────

    def on_click(self, event) -> None:
        widget = getattr(event, "widget", None)
        widget_id = getattr(widget, "id", None)
        if widget_id == "ws-btn-sidebar":
            self.action_toggle_sidebar()
        elif widget_id == "ws-btn-close":
            self.action_close()
        elif widget_id == "ws-btn-unified":
            self._set_diff_mode("unified")
        elif widget_id == "ws-btn-split":
            self._set_diff_mode("split")

    # ── Actions (keyboard twins) ───────────────────────────────

    def action_toggle_sidebar(self) -> None:
        try:
            sidebar = self.query_one("#ws-sidebar", Vertical)
        except Exception:
            return
        self._set_sidebar(not sidebar.display)

    def _set_sidebar(self, visible: bool, *, move_focus: bool = True) -> None:
        try:
            sidebar = self.query_one("#ws-sidebar", Vertical)
        except Exception:
            return
        if not visible:
            # Remember which section had focus so we can restore it on show.
            focused = self.app.focused
            if focused is not None and focused.id in ("ws-projects", "ws-changes", "ws-tree"):
                self._last_sidebar_focus = focused.id
        sidebar.display = visible
        type(self)._sidebar_visible_pref = visible
        if not move_focus:
            return
        if visible:
            self.action_focus_section(self._last_sidebar_focus)
        else:
            # Never leave focus trapped in a hidden widget.
            self.action_focus_section("ws-content")

    def _set_diff_mode(self, mode: str) -> None:
        if mode not in ("unified", "split") or mode == self._diff_mode:
            return
        self._diff_mode = mode
        type(self)._diff_mode_pref = mode
        self._update_diff_toggle_classes()
        self._render_diff()

    def action_toggle_diff_mode(self) -> None:
        if self._diff_text is None:
            return
        self._set_diff_mode("split" if self._diff_mode == "unified" else "unified")

    def action_focus_section(self, section_id: str) -> None:
        if section_id not in _SECTION_IDS:
            return
        try:
            widget = self.query_one(f"#{section_id}")
            if widget.display:
                widget.focus()
        except Exception:
            pass

    def action_edit(self) -> None:
        if self._current_path is None:
            self.app.notify("Nothing open", severity="warning")
            return
        if not self._current_path.is_file():
            self.app.notify("File no longer exists", severity="warning")
            return
        _open_in_editor(self.app, self._current_path)

    def action_close(self) -> None:
        self.dismiss(None)
