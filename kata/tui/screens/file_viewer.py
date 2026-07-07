"""In-TUI file viewers — Markdown (rich) and syntax-highlighted text.

Two modal screens, cmux-style: open a file without leaving Kata.

- ``MarkdownViewerScreen`` renders .md/.markdown with Textual's ``MarkdownViewer``
  (table of contents, in-document navigation for relative .md links, external
  links opened in the browser).
- ``TextViewerScreen`` renders any other text file read-only with Rich
  ``Syntax`` highlighting, guarding against binary and oversized files.

All filesystem reads happen in worker threads (see ``kata/tui/widgets/preview.py``
for the pattern); nothing blocks the UI thread.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import webbrowser
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown, MarkdownViewer, Static

# Guard limits for the text viewer.
MAX_FILE_BYTES = 1024 * 1024  # ~1MB
BINARY_SNIFF_BYTES = 8192  # first 8KB checked for NUL bytes

MARKDOWN_SUFFIXES = {".md", ".markdown"}

# Map file extensions to Rich Syntax lexer names where the suffix alone is
# ambiguous or missing a leading dot. Rich autodetects most from the path, so
# this only needs the awkward cases.
_LEXER_OVERRIDES: dict[str, str] = {
    ".kata": "yaml",
    ".env": "bash",
    "dockerfile": "docker",
    "makefile": "make",
}


def _open_in_editor(app, path: Path) -> None:
    """Suspend the TUI and open ``path`` in ``$EDITOR`` (or a sane fallback).

    Missing/broken editors surface as a toast rather than crashing the app.
    Runs synchronously (it suspends the whole app), so callers invoke it from an
    action handler on the UI thread — the subprocess replaces the terminal.
    """
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        for fallback in ("nano", "vim", "vi"):
            if shutil.which(fallback):
                editor = fallback
                break
    if not editor:
        app.notify("No editor found. Set $EDITOR", severity="error")
        return

    try:
        argv = shlex.split(editor) + [str(path)]
    except ValueError:
        app.notify(f"Invalid $EDITOR: {editor}", severity="error")
        return

    try:
        with app.suspend():
            subprocess.run(argv)
    except FileNotFoundError:
        app.notify(f"Editor not found: {argv[0]}", severity="error")
    except Exception as e:  # noqa: BLE001 — never crash the TUI over an editor
        app.notify(f"Failed to open editor: {e}", severity="error")


def _looks_binary(chunk: bytes) -> bool:
    """A NUL byte in the first chunk is a strong binary signal."""
    return b"\x00" in chunk


def syntax_theme_for(app) -> str:
    """Pick the Rich Syntax theme matching the app's current theme.

    ``ansi_*`` themes inherit the terminal palette so highlighting stays
    legible across all Kata themes (light and dark).
    """
    dark = bool(getattr(app, "current_theme", None) is None or app.current_theme.dark)
    return "ansi_dark" if dark else "ansi_light"


def lexer_for_path(path: Path) -> str:
    """Best-effort Rich lexer name for a file path."""
    name = path.name.lower()
    if name in _LEXER_OVERRIDES:
        return _LEXER_OVERRIDES[name]
    suffix = path.suffix.lower()
    if suffix in _LEXER_OVERRIDES:
        return _LEXER_OVERRIDES[suffix]
    # Let Rich guess from the filename; it maps most known extensions.
    from rich.syntax import Syntax

    try:
        guessed = Syntax.guess_lexer(str(path))
        return guessed or "text"
    except Exception:
        return "text"


def open_url_in_browser(host, href: str) -> None:
    """Open an external URL via ``webbrowser`` in a worker thread.

    ``host`` is any widget/screen with ``run_worker``. Never raises — a slow
    or odd handler must not block or crash the UI thread.
    """

    def _work() -> None:
        try:
            webbrowser.open(href)
        except Exception:
            pass

    host.run_worker(_work, thread=True, exclusive=False, group="browser")


def classify_markdown_link(
    href: str,
    current_path: Path,
    project_root: Path,
) -> tuple[str, Path | None, str]:
    """Classify a Markdown link href for routing. Pure — no UI, no side effects.

    Returns ``(kind, path, anchor)`` where kind is one of:

    - ``"none"``: empty/unusable href — ignore.
    - ``"external"``: http(s)/mailto — open in browser.
    - ``"anchor"``: in-document ``#anchor`` (anchor in the third element).
    - ``"markdown"``: local .md file inside the project (path set).
    - ``"file"``: other local file inside the project (path set).
    - ``"outside"``: resolves outside ``project_root`` — refuse.
    - ``"missing"``: inside the project but not an existing file.
    """
    if not href:
        return "none", None, ""
    if href.startswith(("http://", "https://", "mailto:")):
        return "external", None, ""
    if href.startswith("#"):
        return "anchor", None, href[1:]

    anchor = ""
    target_str = href
    if "#" in href:
        target_str, anchor = href.split("#", 1)
    if not target_str:
        return ("anchor", None, anchor) if anchor else ("none", None, "")

    candidate = Path(target_str)
    if not candidate.is_absolute():
        candidate = current_path.parent / candidate
    try:
        resolved = candidate.resolve()
        root = project_root.resolve()
    except OSError:
        return "none", None, ""

    if not (resolved == root or root in resolved.parents):
        return "outside", resolved, anchor
    if not resolved.is_file():
        return "missing", resolved, anchor
    if resolved.suffix.lower() in MARKDOWN_SUFFIXES:
        return "markdown", resolved, anchor
    return "file", resolved, anchor


def read_text_file(path: Path) -> tuple[str, str | None]:
    """Read a text file, returning ``(kind, payload)``.

    ``kind`` is one of ``"ok"``, ``"binary"``, ``"error"``. For ``"ok"`` the
    payload is the (possibly truncated) file contents; otherwise it is a short
    message. Meant to run inside a worker thread — it does blocking I/O.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(BINARY_SNIFF_BYTES)
            if _looks_binary(head):
                return "binary", None
            rest = fh.read(MAX_FILE_BYTES - len(head) + 1)
        raw = head + rest
    except OSError as e:
        return "error", str(e)

    truncated = len(raw) > MAX_FILE_BYTES
    if truncated:
        raw = raw[:MAX_FILE_BYTES]
    text = raw.decode("utf-8", errors="replace")
    if truncated:
        text += "\n\n… [truncated — file exceeds 1MB]"
    return "ok", text


class TextViewerScreen(ModalScreen[None]):
    """Read-only syntax-highlighted viewer for non-markdown text files."""

    CSS = """
    TextViewerScreen {
        align: center middle;
        background: $background 85%;
    }

    TextViewerScreen #tv-container {
        width: 92%;
        height: 92%;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 0;
    }

    TextViewerScreen #tv-header {
        width: 100%;
        height: 1;
        color: $text;
        background: $panel;
        padding: 0 2;
    }

    TextViewerScreen #tv-scroll {
        width: 100%;
        height: 1fr;
        background: $surface;
        scrollbar-size: 1 1;
        padding: 0 1;
    }

    TextViewerScreen #tv-body {
        width: auto;
        height: auto;
    }

    TextViewerScreen #tv-footer {
        width: 100%;
        height: 1;
        color: $text-muted;
        background: $panel;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Back", show=False),
        Binding("q", "close", "Back", show=False),
        Binding("e", "edit", "Editor", show=False),
    ]

    def __init__(
        self,
        path: Path,
        *,
        goto_line: int | None = None,
    ) -> None:
        super().__init__()
        self.path = Path(path)
        self._goto_line = goto_line

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical

        with Vertical(id="tv-container"):
            yield Static(self._header_text(), id="tv-header")
            with VerticalScroll(id="tv-scroll"):
                yield Static("[dim]Loading…[/dim]", id="tv-body")
            yield Static(
                "[dim]e[/dim] editor   [dim]esc/q[/dim] back",
                id="tv-footer",
            )

    def _header_text(self) -> str:
        name = self.path.name
        home = os.path.expanduser("~")
        display = str(self.path)
        if display.startswith(home):
            display = "~" + display[len(home) :]
        return f"[bold]󰈙 {name}[/bold]  [dim]{display}[/dim]"

    def on_mount(self) -> None:
        self._load()

    def _load(self) -> None:
        """Read the file in a worker thread, then render on the UI thread."""
        path = self.path

        def _work() -> None:
            kind, payload = read_text_file(path)
            self.app.call_from_thread(self._apply_content, kind, payload)

        self.run_worker(_work, thread=True, exclusive=True, group="file_read")

    def _apply_content(self, kind: str, payload: str | None) -> None:
        try:
            body = self.query_one("#tv-body", Static)
        except Exception:
            return

        if kind == "binary":
            body.update(
                "[yellow]󰈤 Binary file[/yellow]\n\n"
                "[dim]This file appears to be binary and can't be shown as text.\n"
                "Press [/dim][dim]e[/dim][dim] to open it in your editor.[/dim]"
            )
            return
        if kind == "error":
            body.update(f"[red]Failed to read file:[/red]\n[dim]{payload}[/dim]")
            return

        from rich.syntax import Syntax

        try:
            syntax = Syntax(
                payload or "",
                lexer_for_path(self.path),
                line_numbers=True,
                word_wrap=False,
                theme=syntax_theme_for(self.app),
                background_color="default",
                indent_guides=False,
            )
            body.update(syntax)
        except Exception:
            # Never let a lexer hiccup blank the screen — fall back to plain text.
            body.update(payload or "")

        if self._goto_line and self._goto_line > 1:
            self._scroll_to_line(self._goto_line)

    def _scroll_to_line(self, line: int) -> None:
        """Best-effort scroll so ``line`` is near the top of the viewport."""
        try:
            scroll = self.query_one("#tv-scroll", VerticalScroll)
            # Lines are 1-based; leave a little context above.
            target = max(0, line - 3)
            scroll.scroll_to(y=target, animate=False)
        except Exception:
            pass

    def action_close(self) -> None:
        self.dismiss(None)

    def action_edit(self) -> None:
        _open_in_editor(self.app, self.path)


class MarkdownViewerScreen(ModalScreen[None]):
    """Markdown viewer with a table of contents and in-document link nav."""

    CSS = """
    MarkdownViewerScreen {
        align: center middle;
        background: $background 85%;
    }

    MarkdownViewerScreen #md-container {
        width: 92%;
        height: 92%;
        background: $surface;
        border: round $surface-lighten-2;
        padding: 0;
    }

    MarkdownViewerScreen #md-header {
        width: 100%;
        height: 1;
        color: $text;
        background: $panel;
        padding: 0 2;
    }

    MarkdownViewerScreen MarkdownViewer {
        width: 100%;
        height: 1fr;
        background: $surface;
    }

    MarkdownViewerScreen #md-footer {
        width: 100%;
        height: 1;
        color: $text-muted;
        background: $panel;
        padding: 0 2;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Back", show=False),
        Binding("q", "close", "Back", show=False),
        Binding("t", "toggle_toc", "TOC", show=False),
        Binding("e", "edit", "Editor", show=False),
    ]

    def __init__(
        self,
        path: Path,
        *,
        project_root: Path | None = None,
    ) -> None:
        super().__init__()
        self.path = Path(path)
        # Confine relative-link navigation to the project (fallback: file's dir).
        self.project_root = Path(project_root) if project_root else self.path.parent

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical

        with Vertical(id="md-container"):
            yield Static(self._header_text(), id="md-header")
            # open_links=False so we intercept every link and decide what to do
            # (in-viewer nav for local .md, browser for http, ignore junk).
            yield MarkdownViewer(show_table_of_contents=True, open_links=False)
            yield Static(
                "[dim]t[/dim] toc   [dim]e[/dim] editor   [dim]esc/q[/dim] back",
                id="md-footer",
            )

    def _header_text(self) -> str:
        name = self.path.name
        home = os.path.expanduser("~")
        display = str(self.path)
        if display.startswith(home):
            display = "~" + display[len(home) :]
        return f"[bold]󰍔 {name}[/bold]  [dim]{display}[/dim]"

    def on_mount(self) -> None:
        self._load(self.path)

    def _load(self, path: Path) -> None:
        """Read markdown in a worker thread, then hand it to the viewer."""

        def _work() -> None:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                kind, payload = "ok", text
            except OSError as e:
                kind, payload = "error", str(e)
            self.app.call_from_thread(self._apply_content, path, kind, payload)

        self.run_worker(_work, thread=True, exclusive=True, group="file_read")

    def _apply_content(self, path: Path, kind: str, payload: str) -> None:
        try:
            viewer = self.query_one(MarkdownViewer)
        except Exception:
            return
        if kind == "error":
            self.run_worker(
                viewer.document.update(f"# Failed to read file\n\n```\n{payload}\n```"),
                exclusive=False,
            )
            return
        # Track the currently-shown file so relative links resolve correctly.
        self.path = path
        try:
            self.query_one("#md-header", Static).update(self._header_text())
        except Exception:
            pass
        # Markdown.update returns an awaitable in this Textual version.
        self.run_worker(viewer.document.update(payload), exclusive=False)

    def on_markdown_viewer_navigator_updated(self, event) -> None:  # pragma: no cover
        """Keep default TOC navigation working (no-op hook for clarity)."""

    def on_markdown_link_clicked(self, event: Markdown.LinkClicked) -> None:
        """Route link clicks: anchors in-doc, http to browser, local .md in-viewer."""
        event.stop()
        kind, resolved, anchor = classify_markdown_link(
            event.href or "", self.path, self.project_root
        )
        if kind == "external":
            open_url_in_browser(self, event.href)
        elif kind == "anchor":
            try:
                self.query_one(MarkdownViewer).document.goto_anchor(anchor)
            except Exception:
                pass
        elif kind == "outside":
            self.app.notify("Link points outside the project", severity="warning")
        elif kind == "missing":
            self.app.notify("Linked file not found", severity="warning")
        elif kind == "markdown":
            self._load(resolved)
        elif kind == "file":
            # Non-markdown local file → open the text viewer on top.
            self.app.push_screen(TextViewerScreen(resolved))

    def action_toggle_toc(self) -> None:
        try:
            viewer = self.query_one(MarkdownViewer)
            viewer.show_table_of_contents = not viewer.show_table_of_contents
        except Exception:
            pass

    def action_close(self) -> None:
        self.dismiss(None)

    def action_edit(self) -> None:
        _open_in_editor(self.app, self.path)


def open_file(app, path: Path, *, project_root: Path | None = None) -> None:
    """Push the right viewer for ``path`` onto ``app``.

    Markdown suffixes → ``MarkdownViewerScreen``; everything else →
    ``TextViewerScreen``. Shared by the file browser and clickable paths.
    """
    path = Path(path)
    if path.suffix.lower() in MARKDOWN_SUFFIXES:
        app.push_screen(MarkdownViewerScreen(path, project_root=project_root))
    else:
        app.push_screen(TextViewerScreen(path))
