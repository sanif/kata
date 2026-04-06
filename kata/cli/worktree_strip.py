"""Worktree manager popup for tmux overlay.

Keybinding: Ctrl+W
Shows worktrees for the current project with session summaries.
Supports create, switch, and delete operations.

Architecture:
  tmux binding → `kata worktree-strip` (calculates size, spawns popup)
               → `kata worktree-strip --popup` (interactive UI inside popup)
"""

import os
import subprocess
import sys
import termios
import tty

from rich.console import Console
from rich.text import Text

from kata.core.constants import SUBPROCESS_TIMEOUT
from kata.core.models import WorktreeStatus

# ── Constants ──────────────────────────────────────────────────────────

_ICON_BRANCH = ""
_ICON_WORKTREE = ""
_MIN_WIDTH = 46


# ── Rendering ────────────────────────────────────────────────────────────


def _content_row(content: Text, width: int) -> Text:
    """Wrap content in box side borders, padding to full width."""
    plain_len = len(content.plain)
    pad = max(0, width - 4 - plain_len)
    t = Text()
    t.append("│ ", "dim")
    t.append_text(content)
    t.append(" " * pad)
    t.append(" │", "dim")
    return t


def _render_worktree_row(
    wt: WorktreeStatus,
    selected: bool,
    is_current: bool,
    avail: int,
) -> tuple[Text, Text | None]:
    """Render a single worktree entry + optional summary line.

    Returns (name_row, summary_row_or_None).
    """
    # ── Status dot ──
    if wt.session_active:
        dot, dot_color = "●", "green"
    else:
        dot, dot_color = "○", "bright_black"

    # ── Display name ──
    if wt.is_main:
        display = wt.info.branch
    else:
        display = wt.info.name

    # ── Git status badge ──
    if wt.dirty:
        if wt.changed_files > 0:
            badge = f"±{wt.changed_files}"
            badge_style = "yellow"
        else:
            badge = "±"
            badge_style = "yellow"
    else:
        badge = "✓"
        badge_style = "green"

    # ── Build name row ──
    entry = Text()

    if selected:
        inner = Text()
        inner.append("┃ ", "cyan")
        inner.append(dot, dot_color)
        inner.append(f" {_ICON_BRANCH} ", "dim")
        inner.append(display, "bold")
        if is_current:
            inner.append("  ‹", "dim cyan")

        # Right-align badge
        name_len = len(inner.plain)
        badge_pad = max(1, avail - name_len - len(badge) - 1)
        inner.append(" " * badge_pad)
        inner.append(badge, badge_style)
        inner.append(" ")
        fill = max(0, avail - len(inner.plain))
        inner.append(" " * fill)
        inner.stylize("on grey23")
        entry.append_text(inner)
    else:
        entry.append("  ")
        entry.append(dot, dot_color)
        entry.append(f" {_ICON_BRANCH} ", "dim")
        if is_current:
            entry.append(display, "dim italic")
            entry.append("  ‹", "dim cyan")
        else:
            entry.append(display)

        name_len = len(entry.plain)
        badge_pad = max(1, avail - name_len - len(badge) - 1)
        entry.append(" " * badge_pad)
        entry.append(badge, f"dim {badge_style}" if not selected else badge_style)
        entry.append(" ")

    # ── Summary row ──
    summary_row = None
    if wt.session_summary:
        summary = Text()
        max_summary = avail - 8  # indent + quotes + pad
        text = wt.session_summary
        if len(text) > max_summary:
            text = text[: max_summary - 1] + "…"
        summary.append(f'      "{text}"', "dim italic")
        summary_row = summary

    return entry, summary_row


def render_worktree_panel(
    worktrees: list[WorktreeStatus],
    selected_index: int,
    project_name: str,
    term_width: int = 50,
    current_worktree: str | None = None,
) -> list[Text]:
    """Render the worktree list as a bordered panel."""
    w = term_width
    lines: list[Text] = []
    avail = w - 4

    # ── Top border with title ──
    title = f" {_ICON_WORKTREE} {project_name} "
    side_len = (w - 2 - len(title)) // 2
    top = Text()
    top.append("╭", "dim")
    top.append("─" * side_len, "dim")
    top.append(title, "bold cyan")
    top.append("─" * (w - 2 - side_len - len(title)), "dim")
    top.append("╮", "dim")
    lines.append(top)

    if not worktrees:
        lines.append(_content_row(Text(""), w))
        empty = Text()
        empty.append("  No worktrees", "dim")
        lines.append(_content_row(empty, w))
        lines.append(_content_row(Text(""), w))
    else:
        # ── Main worktree (always first, separated) ──
        main_wt = worktrees[0] if worktrees and worktrees[0].is_main else None
        other_wts = worktrees[1:] if main_wt else worktrees

        if main_wt:
            lines.append(_content_row(Text(""), w))
            is_current = current_worktree is not None and (
                current_worktree == main_wt.info.name or current_worktree == main_wt.info.branch
            )
            row, summary = _render_worktree_row(main_wt, selected_index == 0, is_current, avail)
            lines.append(_content_row(row, w))
            if summary:
                lines.append(_content_row(summary, w))

        # ── Separator before branches ──
        if other_wts:
            sep_line = Text()
            sep_label = " branches "
            sep_side = (w - 2 - len(sep_label)) // 2
            sep_line.append("├", "dim")
            sep_line.append("─" * sep_side, "dim")
            sep_line.append(sep_label, "dim")
            sep_line.append("─" * (w - 2 - sep_side - len(sep_label)), "dim")
            sep_line.append("┤", "dim")
            lines.append(sep_line)

            for i, wt in enumerate(other_wts):
                idx = i + (1 if main_wt else 0)
                is_current = current_worktree is not None and (
                    current_worktree == wt.info.name or current_worktree == wt.info.branch
                )
                row, summary = _render_worktree_row(wt, selected_index == idx, is_current, avail)
                lines.append(_content_row(row, w))
                if summary:
                    lines.append(_content_row(summary, w))
        elif not main_wt:
            lines.append(_content_row(Text(""), w))

    # ── Spacer ──
    lines.append(_content_row(Text(""), w))

    # ── Separator ──
    sep = Text()
    sep.append("├", "dim")
    sep.append("─" * (w - 2), "dim")
    sep.append("┤", "dim")
    lines.append(sep)

    # ── Hint bar ──
    hint = Text()
    hint.append("  n", "cyan")
    hint.append(" new", "dim")
    hint.append("   ↵", "cyan")
    hint.append(" go", "dim")
    hint.append("   d", "cyan")
    hint.append(" del", "dim")
    hint.append("   esc", "cyan")
    hint.append(" quit", "dim")
    hint_len = len(hint.plain)
    left_pad = max(0, (avail - hint_len) // 2)
    centered_hint = Text()
    centered_hint.append(" " * left_pad)
    centered_hint.append_text(hint)
    lines.append(_content_row(centered_hint, w))

    # ── Bottom border ──
    bot = Text()
    bot.append("╰", "dim")
    bot.append("─" * (w - 2), "dim")
    bot.append("╯", "dim")
    lines.append(bot)

    return lines


def _calc_worktree_popup_size(
    worktrees: list[WorktreeStatus], project_name: str
) -> tuple[int, int]:
    """Calculate popup dimensions."""
    max_name_len = 4  # "main"
    has_branches = False
    for wt in worktrees:
        name_len = len(wt.info.name)
        if wt.is_main:
            name_len = len(wt.info.branch)
        else:
            has_branches = True
        max_name_len = max(max_name_len, name_len)

    # icon(2) + dot(1) + space(1) + branch_icon(2) + name + pad + badge(~4) + borders(4) + selection(2)
    title_w = len(project_name) + 10
    w = max(_MIN_WIDTH, title_w, max_name_len + 22)

    # top(1) + spacer(1) + main(1-2) + sep?(1) + branches(N * 1-2) + spacer(1) + sep(1) + hint(1) + bottom(1)
    content_rows = sum(1 + (1 if wt.session_summary else 0) for wt in worktrees)
    h = content_rows + 6  # borders + spacers + hint
    if has_branches:
        h += 1  # "branches" separator
    return w, h


# ── Input ────────────────────────────────────────────────────────────────


def _read_key() -> str:
    """Read a single keypress in raw terminal mode, blocking."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1)
        if ch == b"\x1b":
            import select as _sel

            r, _, _ = _sel.select([fd], [], [], 0.1)
            if r:
                seq = os.read(fd, 8)
                if seq == b"[A":
                    return "up"
                elif seq == b"[B":
                    return "down"
                return "escape"
            return "escape"
        elif ch in (b"\r", b"\n"):
            return "enter"
        elif ch == b"\x03":
            return "escape"
        return ch.decode("utf-8", errors="replace")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _render_create_panel(
    project_name: str,
    buf: str,
    step: str,  # "name" or "context"
    term_width: int,
) -> list[Text]:
    """Render the create-worktree panel with inline input."""
    w = term_width
    lines: list[Text] = []
    avail = w - 4

    # ── Top border ──
    title = f" {_ICON_WORKTREE} new worktree "
    side = (w - 2 - len(title)) // 2
    top = Text()
    top.append("╭", "dim")
    top.append("─" * side, "dim")
    top.append(title, "bold cyan")
    top.append("─" * (w - 2 - side - len(title)), "dim")
    top.append("╮", "dim")
    lines.append(top)

    lines.append(_content_row(Text(""), w))

    # ── Project context ──
    ctx = Text()
    ctx.append("  from ", "dim")
    ctx.append(project_name, "bold")
    lines.append(_content_row(ctx, w))

    lines.append(_content_row(Text(""), w))

    if step == "name":
        # ── Branch name input ──
        label = Text()
        label.append(f"  {_ICON_BRANCH} branch name", "dim")
        lines.append(_content_row(label, w))

        input_row = Text()
        input_row.append("  > ", "cyan")
        input_row.append(buf, "bold")
        input_row.append("_", "dim")  # cursor
        lines.append(_content_row(input_row, w))
    else:
        # ── Show chosen name ──
        chosen = Text()
        chosen.append(f"  {_ICON_BRANCH} ", "dim")
        chosen.append(buf, "bold")
        lines.append(_content_row(chosen, w))

        lines.append(_content_row(Text(""), w))

        # ── Context mode selection ──
        mode_label = Text()
        mode_label.append("  context mode", "dim")
        lines.append(_content_row(mode_label, w))

        lines.append(_content_row(Text(""), w))

        opt_f = Text()
        opt_f.append("  [", "dim")
        opt_f.append("f", "cyan bold")
        opt_f.append("]", "dim")
        opt_f.append(" fork", "")
        opt_f.append("      carry full Claude session", "dim")
        lines.append(_content_row(opt_f, w))

        opt_s = Text()
        opt_s.append("  [", "dim")
        opt_s.append("s", "cyan bold")
        opt_s.append("]", "dim")
        opt_s.append(" summary", "")
        opt_s.append("   seed with session summary", "dim")
        lines.append(_content_row(opt_s, w))

        opt_c = Text()
        opt_c.append("  [", "dim")
        opt_c.append("c", "cyan bold")
        opt_c.append("]", "dim")
        opt_c.append(" clean", "")
        opt_c.append("     start fresh", "dim")
        lines.append(_content_row(opt_c, w))

    lines.append(_content_row(Text(""), w))

    # ── Separator ──
    sep = Text()
    sep.append("├", "dim")
    sep.append("─" * (w - 2), "dim")
    sep.append("┤", "dim")
    lines.append(sep)

    # ── Hint ──
    hint = Text()
    if step == "name":
        hint.append("  ↵", "cyan")
        hint.append(" confirm", "dim")
        hint.append("   esc", "cyan")
        hint.append(" cancel", "dim")
    else:
        hint.append("  f", "cyan")
        hint.append("/", "dim")
        hint.append("s", "cyan")
        hint.append("/", "dim")
        hint.append("c", "cyan")
        hint.append(" choose", "dim")
        hint.append("   esc", "cyan")
        hint.append(" cancel", "dim")
    hint_len = len(hint.plain)
    left_pad = max(0, (avail - hint_len) // 2)
    centered = Text()
    centered.append(" " * left_pad)
    centered.append_text(hint)
    lines.append(_content_row(centered, w))

    # ── Bottom border ──
    bot = Text()
    bot.append("╰", "dim")
    bot.append("─" * (w - 2), "dim")
    bot.append("╯", "dim")
    lines.append(bot)

    return lines


def _run_create_flow(console: Console, project_name: str) -> tuple[str, str] | None:
    """Interactive create flow. Returns (name, context_mode) or None on cancel."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf: list[str] = []

    try:
        tty.setraw(fd)

        # ── Step 1: branch name ──
        while True:
            # Render panel
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            console.clear()
            panel = _render_create_panel(project_name, "".join(buf), "name", console.width)
            for i, line in enumerate(panel):
                if i < len(panel) - 1:
                    console.print(line)
                else:
                    console.print(line, end="")
            tty.setraw(fd)

            ch = os.read(fd, 1)
            if ch == b"\x1b":
                return None
            elif ch == b"\x03":
                return None
            elif ch in (b"\r", b"\n"):
                if buf:
                    break
            elif ch in (b"\x7f", b"\x08"):
                if buf:
                    buf.pop()
            elif ch.isascii() and ch >= b" ":
                buf.append(ch.decode("utf-8", errors="replace"))

        name = "".join(buf).strip().replace(" ", "-")

        # ── Step 2: context mode ──
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        console.clear()
        panel = _render_create_panel(project_name, name, "context", console.width)
        for i, line in enumerate(panel):
            if i < len(panel) - 1:
                console.print(line)
            else:
                console.print(line, end="")
        tty.setraw(fd)

        ch = os.read(fd, 1)
        if ch == b"\x1b" or ch == b"\x03":
            return None

        mode_map = {b"f": "fork", b"s": "summary", b"c": "fresh"}
        context_mode = mode_map.get(ch, "fresh")

        return name, context_mode

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ── Context seeding ─────────────────────────────────────────────────────


def _seed_context(
    project_path: str,
    wt_path: str,
    wt_info,
    context_mode: str,
) -> None:
    """Seed Claude context in the new worktree based on mode."""
    from kata.utils.claude_sessions import get_current_session_id, get_session_summary

    if context_mode == "fork":
        session_id = get_current_session_id(project_path)
        if session_id:
            # Fork the session — claude will be launched with --resume --fork-session
            # Store the session ID in metadata (already done by caller)
            pass

    elif context_mode == "summary":
        summary = get_session_summary(project_path)
        if summary:
            from pathlib import Path

            context_file = Path(wt_path) / ".claude-context.txt"
            context_file.write_text(f"Previous session context from parent project:\n{summary}\n")


# ── Session management ──────────────────────────────────────────────────


def _get_worktree_session_name(project_name: str, wt_name: str) -> str:
    """Generate tmux session name for a worktree."""
    from kata.utils.paths import sanitize_session_name

    if wt_name == "main":
        return sanitize_session_name(project_name)
    return sanitize_session_name(f"{project_name}:{wt_name}")


def _switch_to_worktree(project_path: str, project_name: str, wt: WorktreeStatus) -> None:
    """Switch to a worktree's tmux session, launching if needed."""
    from pathlib import Path

    from kata.services.sessions import launch_adhoc_session, session_exists

    session_name = _get_worktree_session_name(project_name, wt.info.name)

    if wt.is_main:
        wt_abs = project_path
    else:
        wt_abs = str(Path(project_path) / wt.info.path)

    if session_exists(session_name):
        subprocess.run(
            ["tmux", "switch-client", "-t", session_name],
            capture_output=True,
        )
    else:
        import time

        launch_adhoc_session(wt_abs, session_name=session_name)
        for _ in range(20):
            if session_exists(session_name):
                break
            time.sleep(0.1)
        subprocess.run(
            ["tmux", "switch-client", "-t", session_name],
            capture_output=True,
        )


# ── Popup launcher ──────────────────────────────────────────────────────


def _get_current_project_path() -> str | None:
    """Get the project path of the current tmux session's active pane."""
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{pane_current_path}"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _find_git_root(path: str) -> str | None:
    """Find the git repository root for a path."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _get_current_worktree_name(git_root: str) -> str | None:
    """Detect which worktree we're currently in."""
    from pathlib import Path

    pane_path = _get_current_project_path()
    if not pane_path:
        return None

    pane = Path(pane_path).resolve()
    root = Path(git_root).resolve()

    if pane == root or str(pane).startswith(str(root) + "/") and ".worktrees" not in str(pane):
        return "main"

    # Check if inside a worktree subdirectory
    from kata.services.worktrees import _load_metadata

    for wt in _load_metadata(root):
        wt_abs = (root / wt.path).resolve()
        if pane == wt_abs or str(pane).startswith(str(wt_abs) + "/"):
            return wt.name

    return None


def open_worktree_popup() -> None:
    """Calculate content size and spawn a fitted tmux popup."""
    from pathlib import Path

    pane_path = _get_current_project_path()
    if not pane_path:
        return

    git_root = _find_git_root(pane_path)
    if not git_root:
        return

    from kata.services.worktrees import list_worktrees
    from kata.utils.claude_sessions import get_session_summary

    project_name = Path(git_root).name
    worktrees = list_worktrees(git_root)

    # Fill in session summaries and active status
    from kata.services.sessions import get_all_session_statuses

    statuses = get_all_session_statuses()
    for wt in worktrees:
        session_name = _get_worktree_session_name(project_name, wt.info.name)
        wt.session_active = session_name in statuses

        if wt.is_main:
            wt_abs = git_root
        else:
            wt_abs = str(Path(git_root) / wt.info.path)
        wt.session_summary = get_session_summary(wt_abs)

    w, h = _calc_worktree_popup_size(worktrees, project_name)

    cmd = "kata worktree-strip --popup"
    subprocess.run(
        ["tmux", "display-popup", "-E", "-B", "-w", str(w), "-h", str(h), cmd],
    )


# ── Main loop ────────────────────────────────────────────────────────────


def run_worktree_strip() -> None:
    """Run the interactive worktree manager inside the popup."""
    from pathlib import Path

    from kata.services.sessions import get_all_session_statuses
    from kata.services.worktrees import (
        WorktreeError,
        create_worktree,
        delete_worktree,
        list_worktrees,
    )
    from kata.utils.claude_sessions import get_current_session_id, get_session_summary

    console = Console()

    pane_path = _get_current_project_path()
    if not pane_path:
        console.print("[dim]Not in a project.[/dim]")
        return

    git_root = _find_git_root(pane_path)
    if not git_root:
        console.print("[dim]Not a git repository.[/dim]")
        return

    project_name = Path(git_root).name
    current_wt = _get_current_worktree_name(git_root)

    def _refresh() -> list[WorktreeStatus]:
        wts = list_worktrees(git_root)
        statuses = get_all_session_statuses()
        for wt in wts:
            session_name = _get_worktree_session_name(project_name, wt.info.name)
            wt.session_active = session_name in statuses
            if wt.is_main:
                wt_abs = git_root
            else:
                wt_abs = str(Path(git_root) / wt.info.path)
            wt.session_summary = get_session_summary(wt_abs)
        return wts

    worktrees = _refresh()
    selected = 0
    confirmed = False

    try:
        while True:
            console.clear()
            panel = render_worktree_panel(
                worktrees, selected, project_name, console.width, current_wt
            )
            for i, line in enumerate(panel):
                if i < len(panel) - 1:
                    console.print(line)
                else:
                    console.print(line, end="")

            key = _read_key()

            if key in ("down", "j"):
                selected = (selected + 1) % len(worktrees) if worktrees else 0
            elif key in ("up", "k"):
                selected = (selected - 1) % len(worktrees) if worktrees else 0
            elif key == "enter":
                if worktrees:
                    confirmed = True
                    break
            elif key == "n":
                # ── Create new worktree ──
                result = _run_create_flow(console, project_name)
                if result:
                    name, context_mode = result
                    try:
                        source_id = None
                        if context_mode == "fork":
                            source_id = get_current_session_id(git_root)

                        wt_info = create_worktree(
                            git_root,
                            name,
                            context_mode=context_mode,
                            source_session_id=source_id,
                        )

                        # Seed context
                        wt_abs = str(Path(git_root) / wt_info.path)
                        _seed_context(git_root, wt_abs, wt_info, context_mode)

                        # Refresh and select new worktree
                        worktrees = _refresh()
                        for idx, wt in enumerate(worktrees):
                            if wt.info.name == name:
                                selected = idx
                                break

                    except WorktreeError as e:
                        console.clear()
                        console.print(f"  [red]error:[/red] {e}")
                        _read_key()

                worktrees = _refresh()
                selected = min(selected, len(worktrees) - 1) if worktrees else 0

            elif key == "d":
                if worktrees and not worktrees[selected].is_main:
                    try:
                        delete_worktree(git_root, worktrees[selected].info.name)
                        worktrees = _refresh()
                        selected = min(selected, len(worktrees) - 1) if worktrees else 0
                    except WorktreeError as e:
                        console.clear()
                        console.print(f"  [red]error:[/red] {e}")
                        _read_key()

            elif key == "D":
                if worktrees and not worktrees[selected].is_main:
                    try:
                        delete_worktree(git_root, worktrees[selected].info.name, force=True)
                        worktrees = _refresh()
                        selected = min(selected, len(worktrees) - 1) if worktrees else 0
                    except WorktreeError as e:
                        console.clear()
                        console.print(f"  [red]error:[/red] {e}")
                        _read_key()

            elif key in ("q", "escape"):
                break

    finally:
        console.clear()

    if confirmed and worktrees:
        _switch_to_worktree(git_root, project_name, worktrees[selected])
