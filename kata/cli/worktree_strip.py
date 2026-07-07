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
from pathlib import Path

from rich.text import Text

from kata.cli._termui import (
    FrameRenderer,
    content_row,
    guard_tty,
    raw_screen,
    read_key,
)
from kata.core.constants import (
    SESSION_READY_MAX_RETRIES,
    SESSION_READY_POLL_INTERVAL,
    SUBPROCESS_TIMEOUT,
    WORKTREE_SPINNER_INTERVAL,
)
from kata.core.models import WorktreeStatus


def _display_message(msg: str) -> None:
    """Surface a one-line status in the tmux status bar (launcher context)."""
    try:
        subprocess.run(
            ["tmux", "display-message", msg],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


# ── Constants ──────────────────────────────────────────────────────────

_ICON_BRANCH = ""
_ICON_WORKTREE = ""
_MIN_WIDTH = 46
_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


# ── Rendering ────────────────────────────────────────────────────────────


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
        lines.append(content_row(Text(""), w))
        empty = Text()
        empty.append("  No worktrees", "dim")
        lines.append(content_row(empty, w))
        lines.append(content_row(Text(""), w))
    else:
        # ── Main worktree (always rendered first, wherever it sits in the
        # list) so the Alt+Tab reorder can never mislabel main under
        # "branches". selected_index still refers to positions in the list, so
        # highlighting is resolved by identity.
        main_wt = next((wt for wt in worktrees if wt.is_main), None)
        other_wts = [wt for wt in worktrees if not wt.is_main]

        if main_wt:
            lines.append(content_row(Text(""), w))
            is_current = current_worktree is not None and (
                current_worktree == main_wt.info.name or current_worktree == main_wt.info.branch
            )
            main_idx = worktrees.index(main_wt)
            row, summary = _render_worktree_row(
                main_wt, selected_index == main_idx, is_current, avail
            )
            lines.append(content_row(row, w))
            if summary:
                lines.append(content_row(summary, w))

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

            for wt in other_wts:
                idx = worktrees.index(wt)
                is_current = current_worktree is not None and (
                    current_worktree == wt.info.name or current_worktree == wt.info.branch
                )
                row, summary = _render_worktree_row(wt, selected_index == idx, is_current, avail)
                lines.append(content_row(row, w))
                if summary:
                    lines.append(content_row(summary, w))
        elif not main_wt:
            lines.append(content_row(Text(""), w))

    # ── Spacer ──
    lines.append(content_row(Text(""), w))

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
    hint.append("   C-w", "cyan")
    hint.append(" next", "dim")
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
    lines.append(content_row(centered_hint, w))

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


def _render_create_panel(
    project_name: str,
    buf: str,
    step: str,  # "name" or "context"
    term_width: int,
    has_claude: bool = False,
    message: str | None = None,
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

    lines.append(content_row(Text(""), w))

    # ── Project context ──
    ctx = Text()
    ctx.append("  from ", "dim")
    ctx.append(project_name, "bold")
    lines.append(content_row(ctx, w))

    lines.append(content_row(Text(""), w))

    if step == "name":
        # ── Branch name input ──
        label = Text()
        label.append(f"  {_ICON_BRANCH} branch name", "dim")
        lines.append(content_row(label, w))

        input_row = Text()
        input_row.append("  > ", "cyan")
        input_row.append(buf, "bold")
        input_row.append("_", "dim")  # cursor
        lines.append(content_row(input_row, w))

        if message:
            lines.append(content_row(Text(""), w))
            err = Text()
            err.append(f"  {message}", "yellow")
            lines.append(content_row(err, w))
    else:
        # ── Show chosen name ──
        chosen = Text()
        chosen.append(f"  {_ICON_BRANCH} ", "dim")
        chosen.append(buf, "bold")
        lines.append(content_row(chosen, w))

        lines.append(content_row(Text(""), w))

        # ── Context mode selection ──
        mode_label = Text()
        mode_label.append("  claude context", "dim")
        lines.append(content_row(mode_label, w))

        lines.append(content_row(Text(""), w))

        if has_claude:
            opt_f = Text()
            opt_f.append("  [", "dim")
            opt_f.append("f", "cyan bold")
            opt_f.append("]", "dim")
            opt_f.append(" fork", "")
            opt_f.append("      carry full session", "dim")
            lines.append(content_row(opt_f, w))

            opt_s = Text()
            opt_s.append("  [", "dim")
            opt_s.append("s", "cyan bold")
            opt_s.append("]", "dim")
            opt_s.append(" summary", "")
            opt_s.append("   seed with summary", "dim")
            lines.append(content_row(opt_s, w))

        opt_c = Text()
        opt_c.append("  [", "dim")
        opt_c.append("c", "cyan bold")
        opt_c.append("]", "dim")
        opt_c.append(" clean", "")
        if has_claude:
            opt_c.append("     no Claude context", "dim")
        else:
            opt_c.append("     start fresh", "dim")
        lines.append(content_row(opt_c, w))

        if not has_claude:
            lines.append(content_row(Text(""), w))
            no_claude = Text()
            no_claude.append("  no active Claude session", "dim italic")
            lines.append(content_row(no_claude, w))

    lines.append(content_row(Text(""), w))

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
        if has_claude:
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
    lines.append(content_row(centered, w))

    # ── Bottom border ──
    bot = Text()
    bot.append("╰", "dim")
    bot.append("─" * (w - 2), "dim")
    bot.append("╯", "dim")
    lines.append(bot)

    return lines


def _run_create_flow(
    fd: int, renderer: FrameRenderer, width: int, project_name: str, git_root: str
) -> tuple[str, str] | None:
    """Interactive create flow. Returns (name, context_mode) or None on cancel.

    Runs inside the caller's raw-mode screen. Only shows fork/summary options
    when an active Claude session exists for this project.
    """
    from kata.core.config import get_project_config_path

    buf: list[str] = []
    message: str | None = None

    # Detect if Claude is active for this project
    has_claude = _has_claude_session(git_root) and _config_has_claude(
        get_project_config_path(git_root)
    )

    def _paint(step: str, buf_str: str, msg: str | None = None) -> None:
        frame = renderer.render(
            _render_create_panel(project_name, buf_str, step, width, has_claude, msg)
        )
        sys.stdout.write("\x1b[H")
        sys.stdout.write(frame)
        sys.stdout.flush()

    # ── Step 1: branch name ──
    _paint("name", "")
    while True:
        key = read_key(fd)
        if key == "escape":
            return None
        elif key == "enter":
            candidate = "".join(buf).strip()
            if not candidate:
                message = "branch name cannot be empty"
                _paint("name", "".join(buf), message)
                continue
            break
        elif key == "backspace":
            if buf:
                buf.pop()
            message = None
            _paint("name", "".join(buf), message)
        elif key == "space":
            buf.append(" ")
            message = None
            _paint("name", "".join(buf), message)
        elif key in ("up", "down", "left", "right", "tab", "shift+tab"):
            # Ignore navigation keys during text entry — they must not cancel
            # the flow nor leak escape bytes into the next read.
            continue
        elif len(key) == 1 and key.isprintable():
            buf.append(key)
            message = None
            _paint("name", "".join(buf), message)

    name = "".join(buf).strip().replace(" ", "-")

    # ── Step 2: context mode ──
    _paint("context", name)
    key = read_key(fd)
    if key == "escape":
        return None

    if has_claude:
        mode_map = {"f": "fork", "s": "summary", "c": "fresh"}
    else:
        mode_map = {"c": "fresh"}
    context_mode = mode_map.get(key, "fresh")

    return name, context_mode


# ── Loading panel ───────────────────────────────────────────────────────


def _render_loading_panel(
    project_name: str,
    wt_name: str,
    status: str,
    spinner_frame: int,
    term_width: int,
) -> list[Text]:
    """Render a bordered loading panel with animated spinner."""
    w = term_width
    lines: list[Text] = []

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

    lines.append(content_row(Text(""), w))

    # ── Branch name ──
    branch = Text()
    branch.append(f"  {_ICON_BRANCH} ", "dim")
    branch.append(wt_name, "bold")
    lines.append(content_row(branch, w))

    lines.append(content_row(Text(""), w))

    # ── Spinner + status ──
    frame = _SPINNER_FRAMES[spinner_frame % len(_SPINNER_FRAMES)]
    spinner = Text()
    spinner.append(f"  {frame} ", "cyan")
    spinner.append(status, "dim")
    lines.append(content_row(spinner, w))

    lines.append(content_row(Text(""), w))

    # ── Bottom border ──
    bot = Text()
    bot.append("╰", "dim")
    bot.append("─" * (w - 2), "dim")
    bot.append("╯", "dim")
    lines.append(bot)

    return lines


def _run_full_create_with_spinner(
    renderer: FrameRenderer,
    width: int,
    project_name: str,
    git_root: str,
    name: str,
    context_mode: str,
    source_id: str | None,
    create_fn,
    refresh_fn,
) -> None:
    """Run full worktree creation + seed + switch with animated spinner.

    Runs inside the caller's raw-mode screen; frames are painted with a
    home-cursor repaint rather than clear+print so nothing flickers and no
    traceback vanishes with the popup on failure (the caller surfaces it).
    """
    import threading
    import time

    from kata.services.worktrees import WORKTREES_DIR

    status_text = "creating worktree..."
    error_ref: list[Exception] = []
    done = threading.Event()
    frame = [0]

    def _work():
        nonlocal status_text
        try:
            # Step 1: create worktree
            status_text = "creating worktree..."
            create_fn(
                git_root,
                name,
                context_mode=context_mode,
                source_session_id=source_id,
            )

            # Step 2: seed context
            if context_mode != "fresh":
                status_text = f"seeding context ({context_mode})..."
                wt_abs = str(Path(git_root) / f"{WORKTREES_DIR}/{name}")
                from kata.services.worktrees import _load_metadata

                wt_info = next(
                    (w for w in _load_metadata(Path(git_root)) if w.name == name),
                    None,
                )
                if wt_info:
                    _seed_context(git_root, wt_abs, wt_info, context_mode, source_id)

            # Step 3: launch session
            status_text = "launching session..."
            worktrees = refresh_fn()
            selected_wt = None
            for wt in worktrees:
                if wt.info.name == name:
                    selected_wt = wt
                    break

            if selected_wt:
                _switch_to_worktree(git_root, project_name, selected_wt, context_mode, source_id)

            status_text = "done"
        except Exception as e:
            error_ref.append(e)
        finally:
            done.set()

    worker = threading.Thread(target=_work, daemon=True)
    worker.start()

    while not done.is_set():
        panel = _render_loading_panel(project_name, name, status_text, frame[0], width)
        sys.stdout.write("\x1b[H")
        sys.stdout.write(renderer.render(panel))
        sys.stdout.flush()
        frame[0] += 1
        time.sleep(WORKTREE_SPINNER_INTERVAL)

    worker.join()

    if error_ref:
        raise error_ref[0]


# ── Claude detection ────────────────────────────────────────────────────


def _has_claude_session(project_path: str) -> bool:
    """Check if there's an active Claude Code session for this project."""
    from kata.utils.claude_sessions import get_current_session_id

    return get_current_session_id(project_path) is not None


def _config_has_claude(config_path: str | Path) -> bool:
    """Check if a .kata.yaml config has any panes running claude."""
    path = Path(config_path)
    if not path.exists():
        return False
    try:
        import yaml

        config = yaml.safe_load(path.read_text())
        for window in config.get("windows", []):
            for pane in window.get("panes", []):
                if isinstance(pane, dict):
                    cmds = pane.get("shell_command", [])
                    if isinstance(cmds, list):
                        for cmd in cmds:
                            if isinstance(cmd, str) and "claude" in cmd:
                                return True
                elif isinstance(pane, str) and "claude" in pane:
                    return True
    except Exception:
        pass
    return False


# ── Context seeding ─────────────────────────────────────────────────────


def _seed_context(
    project_path: str,
    wt_path: str,
    wt_info,
    context_mode: str,
    source_session_id: str | None = None,
) -> None:
    """Seed Claude context in the new worktree based on mode.

    Fork: uses `claude --resume <id> --fork-session` in the worktree's
    claude panes (injected by _launch_worktree_session).
    Also writes orientation .claude/CLAUDE.md.

    Summary: writes session summary to .claude/CLAUDE.md where
    Claude Code auto-discovers it.
    """
    from kata.utils.claude_sessions import get_session_summary

    branch = wt_info.branch if hasattr(wt_info, "branch") else "unknown"

    if context_mode == "fork" and source_session_id:
        from kata.utils.claude_sessions import _encode_cwd

        claude_dir = Path.home() / ".claude"
        src_encoded = _encode_cwd(project_path)
        src_session_dir = claude_dir / "projects" / src_encoded
        src_session = src_session_dir / f"{source_session_id}.jsonl"

        if src_session.exists():
            wt_resolved = str(Path(wt_path).resolve())
            dst_encoded = _encode_cwd(wt_resolved)
            dst_session_dir = claude_dir / "projects" / dst_encoded
            dst_session_dir.mkdir(parents=True, exist_ok=True)
            dst_session = dst_session_dir / f"{source_session_id}.jsonl"

            try:
                import shutil

                shutil.copy2(str(src_session), str(dst_session))
            except OSError:
                pass

        # Write orientation context
        wt_claude_dir = Path(wt_path) / ".claude"
        wt_claude_dir.mkdir(exist_ok=True)
        orientation = wt_claude_dir / "CLAUDE.md"
        orientation.write_text(
            f"# Worktree Context\n\n"
            f"This is a worktree forked from the main project.\n"
            f"Branch: {branch}\n"
            f"Parent: {project_path}\n\n"
            f"File paths from the parent conversation exist at the same "
            f"relative paths here.\n"
        )

    elif context_mode == "summary":
        summary = get_session_summary(project_path)
        if summary:
            wt_claude_dir = Path(wt_path) / ".claude"
            wt_claude_dir.mkdir(exist_ok=True)
            orientation = wt_claude_dir / "CLAUDE.md"
            orientation.write_text(
                f"# Worktree Context\n\n"
                f"This worktree was created from the main project.\n"
                f"Branch: {branch}\n"
                f"Parent: {project_path}\n\n"
                f"## Previous Session Summary\n\n"
                f"{summary}\n"
            )


# ── Session management ──────────────────────────────────────────────────


def _get_worktree_session_name(project_name: str, wt_name: str) -> str:
    """Generate tmux session name for a worktree."""
    from kata.utils.paths import sanitize_session_name

    if wt_name == "main":
        return sanitize_session_name(project_name)
    return sanitize_session_name(f"{project_name}:{wt_name}")


def _launch_worktree_session(
    wt_abs: str,
    session_name: str,
    context_mode: str = "fresh",
    source_session_id: str | None = None,
) -> str:
    """Launch a tmux session for a worktree, using parent's .kata.yaml if available.

    If context_mode is "fork" and source_session_id is set, any panes that run
    `claude` will be rewritten to `claude --resume <id> --fork-session` so the
    forked session starts automatically.

    Falls back to adhoc session (auto-detected project type) if no config exists.
    """
    import tempfile

    import yaml

    from kata.core.config import get_project_config_path
    from kata.services.sessions import launch_adhoc_session

    config_path = get_project_config_path(wt_abs)
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text())
            config["session_name"] = session_name
            config["start_directory"] = wt_abs

            for window in config.get("windows", []):
                if "start_directory" not in window:
                    window["start_directory"] = wt_abs
                for pane in window.get("panes", []):
                    if isinstance(pane, dict):
                        if "start_directory" not in pane:
                            pane["start_directory"] = wt_abs
                        # Inject --fork-session into claude panes
                        cmds = pane.get("shell_command", [])
                        if isinstance(cmds, list):
                            pane["shell_command"] = [
                                _rewrite_claude_cmd(cmd, context_mode, source_session_id)
                                for cmd in cmds
                            ]

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", prefix="kata-wt-", delete=False
            ) as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
                temp_path = f.name

            try:
                result = subprocess.run(
                    ["tmuxp", "load", "-d", temp_path],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    return launch_adhoc_session(wt_abs, session_name=session_name)
                return session_name
            finally:
                Path(temp_path).unlink(missing_ok=True)
        except Exception:
            return launch_adhoc_session(wt_abs, session_name=session_name)
    else:
        return launch_adhoc_session(wt_abs, session_name=session_name)


def _rewrite_claude_cmd(cmd: str, context_mode: str, source_session_id: str | None) -> str:
    """Rewrite a pane command if it's `claude` and we need to inject context flags.

    Uses --resume <id> --fork-session for fork mode. The parent session's
    JSONL is copied to the worktree's Claude project dir beforehand.
    """
    if not isinstance(cmd, str):
        return cmd

    stripped = cmd.strip()
    if stripped == "claude" or stripped.startswith("claude "):
        if context_mode == "fork" and source_session_id:
            return f"claude --resume {source_session_id} --fork-session"
        elif context_mode == "summary":
            return "claude --continue"
    return cmd


def _switch_to_worktree(
    project_path: str,
    project_name: str,
    wt: WorktreeStatus,
    context_mode: str = "fresh",
    source_session_id: str | None = None,
) -> None:
    """Switch to a worktree's tmux session, launching if needed."""
    from kata.services.sessions import session_exists

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

        _launch_worktree_session(wt_abs, session_name, context_mode, source_session_id)
        for _ in range(SESSION_READY_MAX_RETRIES):
            if session_exists(session_name):
                break
            time.sleep(SESSION_READY_POLL_INTERVAL)
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
    """Find the main git repository root, resolving through worktrees.

    Inside a worktree, `--show-toplevel` returns the worktree's path, not the
    main repo. We use `--git-common-dir` to find the shared .git directory,
    then resolve the main repo root from that.
    """

    try:
        # Get the common .git dir (shared across all worktrees)
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        if result.returncode != 0:
            return None

        git_common = result.stdout.strip()

        # If it's just ".git", we're in the main repo — use --show-toplevel
        if git_common == ".git":
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=path,
                capture_output=True,
                text=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None

        # Otherwise git_common is an absolute or relative path like
        # /main-repo/.git or ../../.git — the main repo is its parent
        git_common_path = Path(git_common)
        if not git_common_path.is_absolute():
            git_common_path = (Path(path) / git_common_path).resolve()
        return str(git_common_path.parent)

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _get_current_worktree_name(git_root: str) -> str | None:
    """Detect which worktree we're currently in."""
    pane_path = _get_current_project_path()
    if not pane_path:
        return None

    pane = Path(pane_path).resolve()
    root = Path(git_root).resolve()

    if pane == root or (str(pane).startswith(str(root) + "/") and ".worktrees" not in str(pane)):
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
    pane_path = _get_current_project_path()
    if not pane_path:
        _display_message("kata: not in a git repository")
        return

    git_root = _find_git_root(pane_path)
    if not git_root:
        _display_message("kata: not in a git repository")
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

    from kata.services.sessions import get_all_session_statuses
    from kata.services.worktrees import (
        WorktreeError,
        create_worktree,
        delete_worktree,
        list_worktrees,
    )
    from kata.utils.claude_sessions import get_current_session_id, get_session_summary

    guard_tty()

    pane_path = _get_current_project_path()
    if not pane_path:
        print("kata: not in a project", file=sys.stderr)
        return

    git_root = _find_git_root(pane_path)
    if not git_root:
        print("kata: not in a git repository", file=sys.stderr)
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

    # Reorder: move the current worktree to position 1 (Alt+Tab style) so
    # pressing Ctrl+W once selects the previous worktree. Never displace main
    # from index 0 — rendering keeps it pinned at the top regardless, but
    # keeping it at 0 also keeps the selection math intuitive.
    if current_wt and len(worktrees) > 1:
        current_idx = None
        for i, wt in enumerate(worktrees):
            if wt.info.name == current_wt or wt.info.branch == current_wt:
                current_idx = i
                break
        if current_idx is not None and current_idx != 1 and not worktrees[current_idx].is_main:
            current_item = worktrees.pop(current_idx)
            worktrees.insert(1, current_item)

    selected = 0
    confirmed = False

    try:
        w = os.get_terminal_size().columns
    except OSError:
        w, _ = _calc_worktree_popup_size(worktrees, project_name)

    renderer = FrameRenderer(w)

    def _paint() -> None:
        frame = renderer.render(
            render_worktree_panel(worktrees, selected, project_name, w, current_wt)
        )
        sys.stdout.write("\x1b[H")
        sys.stdout.write(frame)
        sys.stdout.flush()

    def _show_and_wait(fd: int, msg: str, *, style: str = "31") -> str:
        """Clear, show a one-line message, and block for a keypress."""
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write(f"\r\n  \x1b[{style}m{msg}\x1b[0m\r\n")
        sys.stdout.flush()
        return read_key(fd)

    with raw_screen() as fd:
        _paint()

        while True:
            key = read_key(fd)

            if key in ("ctrl+w", "down", "j"):
                selected = (selected + 1) % len(worktrees) if worktrees else 0
            elif key in ("up", "k"):
                selected = (selected - 1) % len(worktrees) if worktrees else 0
            elif key == "enter":
                if worktrees:
                    confirmed = True
                    break
            elif key == "n":
                # ── Create new worktree ──
                result = _run_create_flow(fd, renderer, w, project_name, git_root)
                if result:
                    name, context_mode = result
                    try:
                        source_id = None
                        if context_mode == "fork":
                            # Use actual pane path first (user may be in a worktree),
                            # fall back to git root
                            source_id = get_current_session_id(pane_path) or get_current_session_id(
                                git_root
                            )

                        _run_full_create_with_spinner(
                            renderer=renderer,
                            width=w,
                            project_name=project_name,
                            git_root=git_root,
                            name=name,
                            context_mode=context_mode,
                            source_id=source_id,
                            create_fn=create_worktree,
                            refresh_fn=_refresh,
                        )
                        return

                    except WorktreeError as e:
                        # Friendly, expected failure (bad name, git conflict, …).
                        _show_and_wait(fd, f"error: {e}")
                    except Exception as e:  # noqa: BLE001
                        # SessionError / OSError / YAML errors etc. would
                        # otherwise dump a traceback that vanishes with the
                        # popup. Show it and wait so the user can read it.
                        _show_and_wait(fd, f"worktree creation failed: {e}")

                worktrees = _refresh()
                selected = min(selected, len(worktrees) - 1) if worktrees else 0

            elif key in ("d", "D"):
                if worktrees and not worktrees[selected].is_main:
                    wt_name = worktrees[selected].info.name
                    force = key == "D"
                    try:
                        warning = delete_worktree(git_root, wt_name, force=force)
                        worktrees = _refresh()
                        selected = min(selected, len(worktrees) - 1) if worktrees else 0
                        if warning:
                            # Worktree removed but its branch could not be
                            # deleted — surface the warning.
                            _show_and_wait(fd, warning, style="33")
                    except WorktreeError as e:
                        # Offer force delete.
                        retry_key = _show_and_wait(
                            fd,
                            f"error: {e}\r\n\r\n  \x1b[36mD\x1b[0m force delete   "
                            "\x1b[2many other key to cancel\x1b[0m",
                        )
                        if retry_key == "D":
                            try:
                                warning = delete_worktree(git_root, wt_name, force=True)
                                worktrees = _refresh()
                                selected = min(selected, len(worktrees) - 1) if worktrees else 0
                                if warning:
                                    _show_and_wait(fd, warning, style="33")
                            except WorktreeError as e2:
                                _show_and_wait(fd, f"force delete failed: {e2}")

            elif key in ("q", "escape"):
                break

            else:
                continue

            _paint()

    if confirmed and worktrees:
        _switch_to_worktree(git_root, project_name, worktrees[selected])
