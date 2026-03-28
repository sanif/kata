"""Notification popup for tmux overlay — matches switch-strip UI pattern.

Left column: project list with unread counts.
Right column: notification list for the selected project.

Architecture:
  tmux binding → `kata notify-popup` (calculates size, spawns popup with -B)
               → `kata notify-popup --popup` (interactive UI inside popup)
"""

import os
import select as _sel
import subprocess
import sys
import termios
import tty
from datetime import datetime
from io import StringIO

from rich.console import Console
from rich.text import Text

from kata.core.constants import SUBPROCESS_TIMEOUT
from kata.services.notifications.models import (
    Notification,
    NotificationStatus,
)
from kata.utils.notifications import TYPE_ICONS, escape_rich, load_grouped, time_ago

# ── Data ────────────────────────────────────────────────────────────────


def _get_message(n: Notification) -> str:
    body = getattr(n, "body", "") or ""
    if isinstance(body, str) and body.strip():
        first_line = body.strip().split("\n")[0].strip()
        if first_line:
            return first_line
    title = getattr(n, "title", "") or ""
    return title if isinstance(title, str) else str(title)


def _get_full_body(n: Notification) -> str:
    """Get the full notification body text."""
    body = getattr(n, "body", "") or ""
    if isinstance(body, str) and body.strip():
        return body.strip()
    title = getattr(n, "title", "") or ""
    return title if isinstance(title, str) else str(title)


def _get_store():
    from kata.services.notifications.store import NotificationStore

    return NotificationStore()


# ── Project item ────────────────────────────────────────────────────────

_MAX_PROJECTS = 15


class _Project:
    def __init__(self, session_name: str, unread: int, total: int, time_str: str):
        self.session_name = session_name
        self.unread = unread
        self.total = total
        self.time_str = time_str


def _build_projects(grouped: dict[str, list[Notification]]) -> list[_Project]:
    projects: list[_Project] = []
    for session_name, notifications in grouped.items():
        unread = sum(1 for n in notifications if n.status == NotificationStatus.UNREAD)
        total = len(notifications)
        ts = notifications[0].timestamp if notifications else datetime.now()
        projects.append(_Project(session_name, unread, total, time_ago(ts)))
    projects.sort(key=lambda p: (-p.unread, -p.total))
    return projects[:_MAX_PROJECTS]


# ── Rendering ───────────────────────────────────────────────────────────

# Layout constants
_LEFT_W = 30  # left column width (inside outer borders)
_RIGHT_W = 48  # right column width
_PANEL_W = _LEFT_W + 1 + _RIGHT_W + 4  # +1 for ║ divider, +4 for outer │ borders
_NOTIF_ROWS = 12  # max notification rows visible in right pane
_DETAIL_ROWS = 8  # max lines for message detail pane


def _pad(text: Text, target_w: int) -> Text:
    """Pad or truncate a Text to exact plain width."""
    diff = target_w - len(text.plain)
    if diff > 0:
        text.append(" " * diff)
    return text


def render_panel(
    projects: list[_Project],
    cursor: int,
    total_unread: int,
    grouped: dict[str, list[Notification]],
    content_rows: int,
    focus: str = "left",  # "left" or "right"
    notif_cursor: int = 0,  # cursor in right column
) -> list[Text]:
    w = _PANEL_W
    lines: list[Text] = []

    # ── Top border ──
    if total_unread > 0:
        title = f" 󰂚 {total_unread} unread "
    else:
        title = " 󰂚 notifications "
    side = (w - 2 - len(title)) // 2
    top = Text()
    top.append("╭", "dim")
    top.append("─" * side, "dim")
    top.append(title, "bold cyan")
    top.append("─" * (w - 2 - side - len(title)), "dim")
    top.append("╮", "dim")
    lines.append(top)

    # ── Column headers ──
    header = Text()
    header.append("│ ", "dim")
    h_left = Text()
    h_left.append("  PROJECTS", "bold dim")
    _pad(h_left, _LEFT_W)
    header.append_text(h_left)
    header.append("│", "dim")
    h_right = Text()
    if projects and 0 <= cursor < len(projects):
        sel_name = projects[cursor].session_name
        h_right.append(f" {sel_name}", "bold")
    else:
        h_right.append(" NOTIFICATIONS", "bold dim")
    _pad(h_right, _RIGHT_W)
    header.append_text(h_right)
    header.append(" │", "dim")
    lines.append(header)

    # ── Header separator ──
    hsep = Text()
    hsep.append("├", "dim")
    hsep.append("─" * _LEFT_W, "dim")
    hsep.append("┼", "dim")
    hsep.append("─" * (_RIGHT_W + 1), "dim")
    hsep.append("┤", "dim")
    lines.append(hsep)

    # ── Get notifications for selected project ──
    notifs: list[Notification] = []
    if projects and 0 <= cursor < len(projects):
        sel_session = projects[cursor].session_name
        notifs = grouped.get(sel_session, [])

    # ── Content rows ──
    for row_i in range(content_rows):
        line = Text()
        line.append("│ ", "dim")

        # Left cell: project row
        left = Text()
        if row_i < len(projects):
            p = projects[row_i]
            is_sel = row_i == cursor

            if is_sel:
                inner = Text()
                if focus == "left":
                    inner.append("┃ ", "cyan")
                else:
                    inner.append("▸ ", "dim")
                if p.unread > 0:
                    inner.append("● ", "cyan")
                else:
                    inner.append("○ ", "bright_black")
                name = p.session_name
                max_n = _LEFT_W - 10
                if len(name) > max_n:
                    name = name[: max_n - 1] + "…"
                inner.append(name, "bold")
                count_s = f"{p.unread:>3}" if p.unread > 0 else "   "
                gap = _LEFT_W - len(inner.plain) - len(count_s)
                inner.append(" " * max(1, gap))
                if p.unread > 0:
                    inner.append(count_s, "bold cyan")
                else:
                    inner.append(count_s)
                _pad(inner, _LEFT_W)
                if focus == "left":
                    inner.stylize("on grey23")
                else:
                    inner.stylize("on grey15")
                left.append_text(inner)
            else:
                left.append("  ")
                if p.unread > 0:
                    left.append("● ", "cyan")
                else:
                    left.append("○ ", "bright_black")
                name = p.session_name
                max_n = _LEFT_W - 10
                if len(name) > max_n:
                    name = name[: max_n - 1] + "…"
                if p.unread > 0:
                    left.append(name)
                else:
                    left.append(name, "dim")
                count_s = f"{p.unread:>3}" if p.unread > 0 else "   "
                gap = _LEFT_W - len(left.plain) - len(count_s)
                left.append(" " * max(1, gap))
                if p.unread > 0:
                    left.append(count_s, "cyan")
                else:
                    left.append(count_s)
                _pad(left, _LEFT_W)
        else:
            _pad(left, _LEFT_W)

        line.append_text(left)
        line.append("│", "dim")

        # Right cell: notification row
        right = Text()
        is_notif_sel = focus == "right" and row_i == notif_cursor
        if row_i < len(notifs):
            n = notifs[row_i]
            icon = TYPE_ICONS.get(n.type, "•")
            msg = escape_rich(_get_message(n)) or "Notification"
            t = time_ago(n.timestamp)
            is_unread = n.status == NotificationStatus.UNREAD

            if is_notif_sel:
                right.append("┃", "cyan")
            else:
                right.append(" ")
            if is_unread:
                right.append(f"{icon} ", "cyan")
            else:
                right.append(f"{icon} ", "bright_black")

            max_msg = _RIGHT_W - 4 - len(t) - 2
            if len(msg) > max_msg:
                msg = msg[: max_msg - 1] + "…"

            if is_unread:
                right.append(msg)
            else:
                right.append(msg, "dim")

            gap = _RIGHT_W - len(right.plain) - len(t) - 1
            right.append(" " * max(1, gap))
            right.append(t, "bright_black")
            right.append(" ")
        elif row_i == 0 and not notifs:
            right.append("  No notifications", "dim")

        _pad(right, _RIGHT_W + 1)  # +1 for trailing border space
        if is_notif_sel and row_i < len(notifs):
            right.stylize("on grey23")
        line.append_text(right)
        line.append("│", "dim")
        lines.append(line)

    # ── Detail pane (always rendered for stable frame height) ──
    dsep = Text()
    dsep.append("├", "dim")
    dsep.append("─" * (w - 2), "dim")
    dsep.append("┤", "dim")
    lines.append(dsep)

    detail_lines_used = 0
    if focus == "right" and notifs and 0 <= notif_cursor < len(notifs):
        sel_notif = notifs[notif_cursor]
        full_body = escape_rich(_get_full_body(sel_notif))

        # Wrap body into lines that fit
        body_w = w - 6  # "│  " + content + "  │"
        body_lines: list[str] = []
        for raw_line in full_body.split("\n"):
            raw_line = raw_line.strip()
            if not raw_line:
                if body_lines:
                    body_lines.append("")
                continue
            while len(raw_line) > body_w:
                brk = raw_line.rfind(" ", 0, body_w)
                if brk <= 0:
                    brk = body_w
                body_lines.append(raw_line[:brk])
                raw_line = raw_line[brk:].lstrip()
            body_lines.append(raw_line)

        shown = body_lines[:_DETAIL_ROWS]
        has_more = len(body_lines) > _DETAIL_ROWS

        for bl in shown:
            detail_line = Text()
            detail_line.append("│  ", "dim")
            detail_line.append(bl)
            _pad(detail_line, w - 2)
            detail_line.append(" │", "dim")
            lines.append(detail_line)
            detail_lines_used += 1

        if has_more:
            more = Text()
            more.append("│  ", "dim")
            more.append(f"… +{len(body_lines) - _DETAIL_ROWS} more lines", "dim")
            _pad(more, w - 2)
            more.append(" │", "dim")
            lines.append(more)
            detail_lines_used += 1
    else:
        # Empty detail: show hint
        hint_detail = Text()
        hint_detail.append("│  ", "dim")
        hint_detail.append("→ to view message details", "dim")
        _pad(hint_detail, w - 2)
        hint_detail.append(" │", "dim")
        lines.append(hint_detail)
        detail_lines_used += 1

    # Pad remaining detail rows to keep frame stable
    # Total detail area = _DETAIL_ROWS + 1 (for possible "more" line)
    total_detail_slots = _DETAIL_ROWS + 1
    for _ in range(total_detail_slots - detail_lines_used):
        empty_d = Text()
        empty_d.append("│ ", "dim")
        _pad(empty_d, w - 2)
        empty_d.append(" │", "dim")
        lines.append(empty_d)

    # ── Bottom separator ──
    bsep = Text()
    bsep.append("├", "dim")
    bsep.append("─" * (w - 2), "dim")
    bsep.append("┤", "dim")
    lines.append(bsep)

    # ── Hint bar ──
    hint = Text()
    hint.append(" ↵", "cyan")
    hint.append(" switch", "dim")
    hint.append("  d", "cyan")
    hint.append(" dismiss", "dim")
    hint.append("  r", "cyan")
    hint.append(" read", "dim")
    hint.append("  R", "cyan")
    hint.append(" all read", "dim")
    hint.append("  esc", "cyan")
    hint.append(" quit", "dim")
    avail = w - 4
    left_pad = max(0, (avail - len(hint.plain)) // 2)
    hline = Text()
    hline.append("│ ", "dim")
    centered = Text()
    centered.append(" " * left_pad)
    centered.append_text(hint)
    _pad(centered, avail)
    hline.append_text(centered)
    hline.append(" │", "dim")
    lines.append(hline)

    # ── Bottom border ──
    bot = Text()
    bot.append("╰", "dim")
    bot.append("─" * (w - 2), "dim")
    bot.append("╯", "dim")
    lines.append(bot)

    return lines


# ── Input ───────────────────────────────────────────────────────────────


def _read_key(fd: int) -> str:
    ch = os.read(fd, 1)
    if ch == b"\x1b":
        r, _, _ = _sel.select([fd], [], [], 0.1)
        if r:
            seq = os.read(fd, 8)
            if seq in (b"[A", b"OA"):
                return "up"
            elif seq in (b"[B", b"OB"):
                return "down"
            elif seq in (b"[C", b"OC"):
                return "right"
            elif seq in (b"[D", b"OD"):
                return "left"
            return "escape"
        return "escape"
    elif ch in (b"\r", b"\n"):
        return "enter"
    elif ch == b" ":
        return "space"
    elif ch == b"\x03":
        return "escape"
    elif ch == b"d":
        return "dismiss"
    elif ch == b"D":
        return "dismiss_all"
    elif ch == b"r":
        return "read"
    elif ch == b"R":
        return "read_all"
    return ch.decode("utf-8", errors="replace")


# ── Popup launcher ──────────────────────────────────────────────────────


def open_notify_popup() -> None:
    """Calculate content size and spawn a fitted borderless tmux popup."""
    grouped = load_grouped()
    projects = _build_projects(grouped)

    content_rows = max(len(projects), _NOTIF_ROWS, 3)

    # top(1) + header(1) + hsep(1) + content(N) + dsep(1) + detail(_DETAIL_ROWS+1) + bsep(1) + hint(1) + bot(1)
    h = content_rows + 6 + 1 + _DETAIL_ROWS + 1
    w = _PANEL_W

    # Cap to 80% of tmux pane, with +1 buffer to prevent clipping
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{pane_height}"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        pane_h = int(result.stdout.strip())
        h = min(h + 1, int(pane_h * 0.85))
    except Exception:
        h = min(h + 1, 35)

    subprocess.run(
        [
            "tmux",
            "display-popup",
            "-E",
            "-B",
            "-w",
            str(w),
            "-h",
            str(h),
            "kata notify-popup --popup",
        ],
    )


# ── Reload helper ───────────────────────────────────────────────────────


def _reload_state():
    grouped = load_grouped()
    projects = _build_projects(grouped)
    total_unread = 0
    for notifs in grouped.values():
        total_unread += sum(1 for n in notifs if n.status == NotificationStatus.UNREAD)
    return grouped, projects, total_unread


# ── Main loop ───────────────────────────────────────────────────────────


def run_notify_popup() -> None:
    """Run the interactive notification popup inside tmux."""
    grouped, projects, total_unread = _reload_state()

    cursor = 0
    notif_cursor = 0
    focus = "left"  # "left" or "right"
    confirmed = False
    term_h = os.get_terminal_size().lines
    content_rows = max(len(projects), _NOTIF_ROWS, 3)
    content_rows = min(content_rows, term_h - 6)

    def _get_notifs():
        if projects and 0 <= cursor < len(projects):
            return grouped.get(projects[cursor].session_name, [])
        return []

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    buf_console = Console(file=StringIO(), force_terminal=True, width=_PANEL_W)

    def _render() -> str:
        panel = render_panel(
            projects,
            cursor,
            total_unread,
            grouped,
            content_rows,
            focus=focus,
            notif_cursor=notif_cursor,
        )
        buf = buf_console.file
        buf.seek(0)
        buf.truncate()
        for line in panel:
            buf_console.print(line, end="")
            buf.write("\r\n")
        return buf.getvalue()

    try:
        tty.setraw(fd)
        sys.stdout.write("\x1b[?25l\x1b[2J\x1b[H")
        sys.stdout.write(_render())
        sys.stdout.flush()

        while True:
            key = _read_key(fd)

            if key == "up":
                if focus == "left":
                    if projects:
                        cursor = (cursor - 1) % len(projects)
                        notif_cursor = 0  # reset right cursor on project change
                else:
                    notifs = _get_notifs()
                    if notifs:
                        notif_cursor = (notif_cursor - 1) % len(notifs)
            elif key == "down":
                if focus == "left":
                    if projects:
                        cursor = (cursor + 1) % len(projects)
                        notif_cursor = 0
                else:
                    notifs = _get_notifs()
                    if notifs:
                        notif_cursor = (notif_cursor + 1) % len(notifs)
            elif key == "right":
                if focus == "left":
                    notifs = _get_notifs()
                    if notifs:
                        focus = "right"
                        notif_cursor = 0
            elif key == "left":
                if focus == "right":
                    focus = "left"
            elif key == "enter":
                confirmed = True
                break
            elif key == "dismiss":
                if focus == "right":
                    # Dismiss single notification
                    notifs = _get_notifs()
                    if notifs and 0 <= notif_cursor < len(notifs):
                        nid = notifs[notif_cursor].id
                        try:
                            store = _get_store()
                            try:
                                store.dismiss(nid)
                            finally:
                                store.close()
                        except Exception:
                            pass
                        grouped, projects, total_unread = _reload_state()
                        content_rows = max(len(projects), _NOTIF_ROWS, 3)
                        content_rows = min(content_rows, term_h - 6)
                        new_notifs = _get_notifs()
                        if notif_cursor >= len(new_notifs):
                            notif_cursor = max(0, len(new_notifs) - 1)
                        if not new_notifs:
                            focus = "left"
                elif projects:
                    # Dismiss all notifications for project
                    session = projects[cursor].session_name
                    try:
                        store = _get_store()
                        try:
                            store.dismiss_by_session(session)
                        finally:
                            store.close()
                    except Exception:
                        pass
                    grouped, projects, total_unread = _reload_state()
                    content_rows = max(len(projects), _NOTIF_ROWS, 3)
                    content_rows = min(content_rows, term_h - 6)
                    if cursor >= len(projects):
                        cursor = max(0, len(projects) - 1)
                    notif_cursor = 0
            elif key == "dismiss_all":
                try:
                    store = _get_store()
                    try:
                        store.dismiss_all()
                    finally:
                        store.close()
                except Exception:
                    pass
                grouped, projects, total_unread = _reload_state()
                content_rows = max(len(projects), _NOTIF_ROWS, 3)
                content_rows = min(content_rows, term_h - 6)
                cursor = 0
                notif_cursor = 0
                focus = "left"
            elif key == "read":
                if focus == "right":
                    # Mark single notification read
                    notifs = _get_notifs()
                    if notifs and 0 <= notif_cursor < len(notifs):
                        nid = notifs[notif_cursor].id
                        try:
                            store = _get_store()
                            try:
                                store.update_status(nid, NotificationStatus.READ)
                            finally:
                                store.close()
                        except Exception:
                            pass
                        grouped, projects, total_unread = _reload_state()
                        content_rows = max(len(projects), _NOTIF_ROWS, 3)
                        content_rows = min(content_rows, term_h - 6)
                elif projects:
                    # Mark all for project read
                    session = projects[cursor].session_name
                    try:
                        store = _get_store()
                        try:
                            store.mark_session_read(session)
                        finally:
                            store.close()
                    except Exception:
                        pass
                    grouped, projects, total_unread = _reload_state()
                    content_rows = max(len(projects), _NOTIF_ROWS, 3)
                    content_rows = min(content_rows, term_h - 6)
                    if cursor >= len(projects):
                        cursor = max(0, len(projects) - 1)
            elif key == "read_all":
                try:
                    store = _get_store()
                    try:
                        store.mark_all_read()
                    finally:
                        store.close()
                except Exception:
                    pass
                grouped, projects, total_unread = _reload_state()
                content_rows = max(len(projects), _NOTIF_ROWS, 3)
                content_rows = min(content_rows, term_h - 6)
                if cursor >= len(projects):
                    cursor = max(0, len(projects) - 1)
                notif_cursor = 0
            elif key == "escape":
                break
            else:
                continue

            sys.stdout.write("\x1b[H")
            sys.stdout.write(_render())
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        sys.stdout.write("\x1b[?25h\x1b[2J\x1b[H")
        sys.stdout.flush()

    if confirmed and projects:
        session_name = projects[cursor].session_name
        try:
            store = _get_store()
            try:
                store.mark_session_read(session_name)
            finally:
                store.close()
        except Exception:
            pass
        subprocess.run(
            ["tmux", "switch-client", "-t", session_name],
            capture_output=True,
        )
