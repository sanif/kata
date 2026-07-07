"""In-TUI file browser — a filtered directory tree rooted at a project.

Opened with ``f`` on the dashboard (or via the context menu). Enter/click opens
a file in the appropriate viewer (markdown or syntax-highlighted text). Noise
directories are hidden by default; ``.`` toggles dotfiles; ``e`` opens the
highlighted file in ``$EDITOR``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Static

from kata.tui.screens.file_viewer import open_file

# Directories that are almost always noise in a project tree.
NOISE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".worktrees",
        "dist",
        "build",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
    }
)


class FilteredDirectoryTree(DirectoryTree):
    """A ``DirectoryTree`` that hides noise dirs and (optionally) dotfiles."""

    def __init__(self, path, *, show_hidden: bool = False, **kwargs) -> None:
        super().__init__(path, **kwargs)
        self.show_hidden = show_hidden

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        result = []
        for p in paths:
            name = p.name
            if name in NOISE_DIRS:
                continue
            if not self.show_hidden and name.startswith("."):
                continue
            result.append(p)
        return result


class FileBrowserScreen(ModalScreen[None]):
    """Modal file browser rooted at a project path."""

    CSS = """
    FileBrowserScreen {
        align: center middle;
        background: $background 85%;
    }

    FileBrowserScreen #fb-container {
        width: 70%;
        max-width: 90;
        height: 88%;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 0;
    }

    FileBrowserScreen #fb-header {
        width: 100%;
        height: 1;
        color: $text;
        background: $panel;
        padding: 0 2;
    }

    FileBrowserScreen DirectoryTree {
        width: 100%;
        height: 1fr;
        background: $surface;
        padding: 0 1;
        scrollbar-size: 1 1;
    }

    FileBrowserScreen DirectoryTree > .directory-tree--folder {
        text-style: bold;
    }

    FileBrowserScreen DirectoryTree > .tree--cursor {
        background: $primary 22%;
    }

    FileBrowserScreen DirectoryTree:focus > .tree--cursor {
        background: $primary 30%;
    }

    FileBrowserScreen #fb-footer {
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
        Binding("full_stop", "toggle_hidden", "Hidden", show=False),
        Binding("e", "edit", "Editor", show=False),
    ]

    def __init__(self, root: Path | str, *, title: str | None = None) -> None:
        super().__init__()
        self.root = Path(root)
        self._title = title or self.root.name
        self._show_hidden = False

    def compose(self) -> ComposeResult:
        with Vertical(id="fb-container"):
            yield Static(self._header_text(), id="fb-header")
            yield FilteredDirectoryTree(str(self.root), show_hidden=self._show_hidden)
            yield Static(self._footer_text(), id="fb-footer")

    def _header_text(self) -> str:
        return f"[bold]󰉋 {self._title}[/bold]  [dim]{self.root}[/dim]"

    def _footer_text(self) -> str:
        hidden_state = "on" if self._show_hidden else "off"
        return (
            "[dim]enter[/dim] open   "
            "[dim]e[/dim] editor   "
            f"[dim].[/dim] hidden ({hidden_state})   "
            "[dim]esc/q[/dim] close"
        )

    def on_mount(self) -> None:
        try:
            self.query_one(FilteredDirectoryTree).focus()
        except Exception:
            pass

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Open the selected file in the appropriate viewer."""
        event.stop()
        open_file(self.app, Path(event.path), project_root=self.root)

    def action_toggle_hidden(self) -> None:
        """Toggle hidden-file visibility by rebuilding the tree."""
        self._show_hidden = not self._show_hidden
        try:
            old = self.query_one(FilteredDirectoryTree)
            container = self.query_one("#fb-container", Vertical)
            new_tree = FilteredDirectoryTree(str(self.root), show_hidden=self._show_hidden)
            old.remove()
            # Mount after the header, before the footer.
            container.mount(new_tree, after=self.query_one("#fb-header", Static))
            new_tree.focus()
        except Exception:
            pass
        try:
            self.query_one("#fb-footer", Static).update(self._footer_text())
        except Exception:
            pass

    def action_edit(self) -> None:
        """Open the highlighted file in $EDITOR (ignores directories)."""
        try:
            tree = self.query_one(FilteredDirectoryTree)
            node = tree.cursor_node
            if node is None or node.data is None:
                return
            path = Path(node.data.path)
            if not path.is_file():
                self.app.notify("Not a file", severity="warning")
                return
        except Exception:
            return
        from kata.tui.screens.file_viewer import _open_in_editor

        _open_in_editor(self.app, path)

    def action_close(self) -> None:
        self.dismiss(None)
