"""In-TUI diff viewer for uncommitted changes, with Claude-edit awareness.

Opened with ``g`` on the dashboard (or "View Changes" in the context menu).
Left panel lists changed files (staged + unstaged + untracked) sorted by mtime,
newest first; the right panel shows the unified diff for the highlighted file.
Files touched by the most recent Claude Code session for the project are badged
with ``✦`` and can be filtered with ``c``.

All git/JSONL work runs in worker threads; nothing blocks the UI thread.
"""

from __future__ import annotations

import os
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from kata.tui.screens.file_viewer import _open_in_editor, open_file, read_text_file
from kata.utils.claude_sessions import get_session_edited_files
from kata.utils.git import ChangedFile, collect_uncommitted_changes, get_uncommitted_diff

# Status letter -> Rich color (plain colors; Tree/OptionList markup can't use
# theme variables like $primary).
_STATUS_COLORS: dict[str, str] = {
    "M": "yellow",
    "A": "green",
    "D": "red",
    "U": "cyan",
    "R": "magenta",
}

_MAX_NAME = 34


def build_untracked_diff(rel_path: str, text: str) -> str:
    """Render an untracked file's content as an all-additions unified diff."""
    lines = text.split("\n")
    # A trailing newline produces one empty trailing element — drop it so we
    # don't show a phantom added line.
    if lines and lines[-1] == "":
        lines = lines[:-1]
    header = [
        f"diff --git a/{rel_path} b/{rel_path}",
        "new file",
        "--- /dev/null",
        f"+++ b/{rel_path}",
        f"@@ -0,0 +1,{len(lines)} @@",
    ]
    return "\n".join(header + [f"+{line}" for line in lines])


class DiffViewerScreen(ModalScreen[None]):
    """Modal viewer for a project's uncommitted changes."""

    CSS = """
    DiffViewerScreen {
        align: center middle;
        background: $background 85%;
    }

    DiffViewerScreen #dv-container {
        width: 94%;
        height: 90%;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 0;
    }

    DiffViewerScreen #dv-header {
        width: 100%;
        height: 1;
        color: $text;
        background: $panel;
        padding: 0 2;
    }

    DiffViewerScreen #dv-body {
        width: 100%;
        height: 1fr;
    }

    DiffViewerScreen #dv-files {
        width: 42%;
        max-width: 60;
        height: 100%;
        background: $surface;
        border-right: vkey $surface-lighten-1;
        scrollbar-size: 1 1;
    }

    DiffViewerScreen #dv-files > .option-list--option-highlighted {
        background: $primary 20%;
        color: $text;
    }

    DiffViewerScreen #dv-diff-scroll {
        width: 1fr;
        height: 100%;
        background: $surface;
        scrollbar-size: 1 1;
        padding: 0 1;
    }

    DiffViewerScreen #dv-diff {
        width: auto;
        height: auto;
    }

    DiffViewerScreen #dv-empty {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
        display: none;
    }

    DiffViewerScreen #dv-footer {
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
        Binding("r", "refresh", "Refresh", show=False),
        Binding("e", "edit", "Editor", show=False),
        Binding("c", "toggle_claude", "Claude only", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, root: Path | str, *, title: str | None = None) -> None:
        super().__init__()
        self.root = Path(root)
        self._title = title or self.root.name
        self._files: list[ChangedFile] = []
        self._visible: list[ChangedFile] = []
        self._claude_paths: set[Path] = set()
        self._claude_only = False
        self._load_gen = 0
        self._diff_gen = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="dv-container"):
            yield Static(self._header_text(), id="dv-header")
            with Horizontal(id="dv-body"):
                yield OptionList(id="dv-files")
                with VerticalScroll(id="dv-diff-scroll"):
                    yield Static("[dim]Loading…[/dim]", id="dv-diff")
            yield Static("", id="dv-empty")
            yield Static(self._footer_text(), id="dv-footer")

    def _header_text(self) -> str:
        home = os.path.expanduser("~")
        display = str(self.root)
        if display.startswith(home):
            display = "~" + display[len(home) :]
        claude = ""
        if self._claude_paths:
            edited = sum(1 for f in self._files if f.path in self._claude_paths)
            if edited:
                claude = f"  [cyan]✦ {edited} claude-edited[/cyan]"
        return f"[bold]󰊢 {self._title}[/bold]  [dim]{display}[/dim]{claude}"

    def _footer_text(self) -> str:
        claude_state = "on" if self._claude_only else "off"
        return (
            "[dim]enter[/dim] open   "
            "[dim]e[/dim] editor   "
            f"[dim]c[/dim] claude ({claude_state})   "
            "[dim]r[/dim] refresh   "
            "[dim]j/k[/dim] move   "
            "[dim]esc/q[/dim] close"
        )

    def on_mount(self) -> None:
        self._load()
        try:
            self.query_one("#dv-files", OptionList).focus()
        except Exception:
            pass

    # ── Loading ────────────────────────────────────────────────

    def _load(self) -> None:
        """Collect changes + Claude-session edits in a worker thread."""
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
            self.app.call_from_thread(self._apply_load, gen, changes, claude_paths)

        self.run_worker(_work, thread=True, exclusive=True, group="diff_load")

    def _apply_load(
        self,
        gen: int,
        changes: list[ChangedFile] | None,
        claude_paths: set[Path],
    ) -> None:
        if gen != self._load_gen:
            return

        if changes is None:
            self._files = []
            self._claude_paths = set()
            self._show_empty("󰊢 Not a git repository")
            return
        if not changes:
            self._files = []
            self._claude_paths = claude_paths
            self._show_empty("󰄬 Working tree clean — nothing to diff")
            return

        self._files = changes
        self._claude_paths = claude_paths
        self._show_list()
        self._rebuild_options()
        try:
            self.query_one("#dv-header", Static).update(self._header_text())
        except Exception:
            pass

    def _show_empty(self, message: str) -> None:
        try:
            self.query_one("#dv-body", Horizontal).display = False
            empty = self.query_one("#dv-empty", Static)
            empty.display = True
            empty.update(f"[dim]{message}[/dim]")
        except Exception:
            pass

    def _show_list(self) -> None:
        try:
            self.query_one("#dv-body", Horizontal).display = True
            self.query_one("#dv-empty", Static).display = False
        except Exception:
            pass

    def _rebuild_options(self) -> None:
        """Fill the file list from ``_files``, honouring the Claude filter."""
        try:
            option_list = self.query_one("#dv-files", OptionList)
        except Exception:
            return
        option_list.clear_options()

        if self._claude_only:
            self._visible = [f for f in self._files if f.path in self._claude_paths]
        else:
            self._visible = list(self._files)

        if not self._visible:
            # Filter active but nothing matched (or no Claude session found).
            option_list.add_option(
                Option("[dim]  no Claude session edits found[/dim]", disabled=True)
            )
            self._set_diff_placeholder("[dim]No files to show[/dim]")
            return

        for changed in self._visible:
            option_list.add_option(Option(self._file_label(changed)))
        option_list.highlighted = 0

    def _file_label(self, changed: ChangedFile) -> str:
        color = _STATUS_COLORS.get(changed.status, "white")
        if changed.added is None and changed.removed is None:
            counts = "[dim]  bin[/dim]"
        else:
            counts = f"[green]+{changed.added or 0}[/green] [red]-{changed.removed or 0}[/red]"
        name = changed.rel_path
        if len(name) > _MAX_NAME:
            name = "…" + name[-(_MAX_NAME - 1) :]
        badge = " [cyan]✦[/cyan]" if changed.path in self._claude_paths else ""
        return f"[{color}]{changed.status}[/{color}] {name}{badge}  {counts}"

    # ── Diff pane ──────────────────────────────────────────────

    @on(OptionList.OptionHighlighted, "#dv-files")
    def _on_file_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        index = event.option_index
        if index is None or not (0 <= index < len(self._visible)):
            return
        self._load_diff(self._visible[index])

    def _load_diff(self, changed: ChangedFile) -> None:
        """Compute the diff text for one file in a worker thread."""
        self._diff_gen += 1
        gen = self._diff_gen
        root = self.root

        def _work() -> None:
            if changed.status == "U":
                kind, payload = read_text_file(changed.path)
                if kind == "binary":
                    text = None
                    note = "Binary file — no text diff"
                elif kind == "error":
                    text = None
                    note = f"Failed to read file: {payload}"
                else:
                    text = build_untracked_diff(changed.rel_path, payload or "")
                    note = ""
            else:
                diff = get_uncommitted_diff(root, changed.rel_path)
                if diff is None:
                    text, note = None, "Failed to compute diff"
                elif not diff.strip():
                    text, note = None, "No textual changes (binary or mode-only)"
                else:
                    text, note = diff, ""
            self.app.call_from_thread(self._apply_diff, gen, text, note)

        self.run_worker(_work, thread=True, exclusive=True, group="diff_render")

    def _apply_diff(self, gen: int, text: str | None, note: str) -> None:
        if gen != self._diff_gen:
            return
        try:
            body = self.query_one("#dv-diff", Static)
            scroll = self.query_one("#dv-diff-scroll", VerticalScroll)
        except Exception:
            return

        if text is None:
            body.update(f"[dim]{note}[/dim]")
            return

        from rich.syntax import Syntax

        # ``ansi_*`` themes inherit the terminal palette (see TextViewerScreen).
        dark = bool(getattr(self.app, "current_theme", None) is None or self.app.current_theme.dark)
        try:
            body.update(
                Syntax(
                    text,
                    "diff",
                    line_numbers=False,
                    word_wrap=False,
                    theme="ansi_dark" if dark else "ansi_light",
                    background_color="default",
                )
            )
        except Exception:
            body.update(text)
        scroll.scroll_to(y=0, animate=False)

    def _set_diff_placeholder(self, markup: str) -> None:
        try:
            self.query_one("#dv-diff", Static).update(markup)
        except Exception:
            pass

    # ── Actions ────────────────────────────────────────────────

    def _highlighted_file(self) -> ChangedFile | None:
        try:
            option_list = self.query_one("#dv-files", OptionList)
            index = option_list.highlighted
        except Exception:
            return None
        if index is None or not (0 <= index < len(self._visible)):
            return None
        return self._visible[index]

    @on(OptionList.OptionSelected, "#dv-files")
    def _on_file_selected(self, event: OptionList.OptionSelected) -> None:
        """Enter on a file opens it in the file viewer."""
        changed = self._highlighted_file()
        if changed is None:
            return
        if not changed.path.is_file():
            self.app.notify("File no longer exists", severity="warning")
            return
        open_file(self.app, changed.path, project_root=self.root)

    def action_edit(self) -> None:
        changed = self._highlighted_file()
        if changed is None:
            return
        if not changed.path.is_file():
            self.app.notify("File no longer exists", severity="warning")
            return
        _open_in_editor(self.app, changed.path)

    def action_refresh(self) -> None:
        self._load()

    def action_toggle_claude(self) -> None:
        self._claude_only = not self._claude_only
        self._rebuild_options()
        try:
            self.query_one("#dv-footer", Static).update(self._footer_text())
        except Exception:
            pass

    def action_cursor_down(self) -> None:
        try:
            self.query_one("#dv-files", OptionList).action_cursor_down()
        except Exception:
            pass

    def action_cursor_up(self) -> None:
        try:
            self.query_one("#dv-files", OptionList).action_cursor_up()
        except Exception:
            pass

    def action_close(self) -> None:
        self.dismiss(None)
