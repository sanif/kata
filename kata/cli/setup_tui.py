"""Interactive TUI for `kata setup`.

Shows all integrations as a toggleable checklist with arrow/space navigation.
"""

import json
import os
import select
import shutil
import subprocess
import sys
import termios
import tty
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

from rich.console import Console
from rich.text import Text

from kata.core.constants import SUBPROCESS_TIMEOUT

# ── Data model ───────────────────────────────────────────────────────────


@dataclass
class SetupItem:
    key: str
    label: str
    description: str
    group: str
    checked: bool = False
    configured: bool = False


@dataclass
class SetupGroup:
    name: str
    items: list[SetupItem] = field(default_factory=list)


# ── Detection ────────────────────────────────────────────────────────────


def _has_kata_hooks(settings_path: Path) -> bool:
    if not settings_path.exists():
        return False
    try:
        data = json.loads(settings_path.read_text())
        for event_hooks in data.get("hooks", {}).values():
            for entry in event_hooks:
                for h in entry.get("hooks", []):
                    if "kata notify" in h.get("command", ""):
                        return True
    except Exception:
        pass
    return False


def _has_codex_notify(config_path: Path) -> bool:
    if not config_path.exists():
        return False
    try:
        return "kata notify-hook codex" in config_path.read_text()
    except Exception:
        return False


def _has_tmux_switcher() -> bool:
    tmux_conf = Path.home() / ".tmux.conf"
    if not tmux_conf.exists():
        return False
    try:
        return "switch-strip" in tmux_conf.read_text()
    except Exception:
        return False


def _has_tmux_notify() -> bool:
    tmux_conf = Path.home() / ".tmux.conf"
    if not tmux_conf.exists():
        return False
    try:
        return "notify-popup" in tmux_conf.read_text()
    except Exception:
        return False


def _has_tmux_detach() -> bool:
    tmux_conf = Path.home() / ".tmux.conf"
    if not tmux_conf.exists():
        return False
    try:
        content = tmux_conf.read_text()
        return "C-q" in content and "detach" in content
    except Exception:
        return False


def _detect_items() -> list[SetupGroup]:
    """Detect current state and build the item list."""
    claude_settings = Path.home() / ".claude" / "settings.json"
    gemini_settings = Path.home() / ".gemini" / "settings.json"
    codex_settings = Path.home() / ".codex" / "config.toml"

    claude_ok = _has_kata_hooks(claude_settings)
    gemini_ok = _has_kata_hooks(gemini_settings)
    codex_ok = _has_codex_notify(codex_settings)
    tn_ok = shutil.which("terminal-notifier") is not None
    switcher_ok = _has_tmux_switcher()
    notify_ok = _has_tmux_notify()
    detach_ok = _has_tmux_detach()

    hooks = SetupGroup(
        "Hooks",
        [
            SetupItem(
                "claude",
                "Claude Code",
                "Stop, SubagentStop, PreToolUse",
                "Hooks",
                checked=claude_ok,
                configured=claude_ok,
            ),
            SetupItem(
                "gemini",
                "Gemini CLI",
                "AfterAgent, BeforeTool, SessionEnd",
                "Hooks",
                checked=gemini_ok,
                configured=gemini_ok,
            ),
            SetupItem(
                "codex",
                "Codex CLI",
                "agent turn notify",
                "Hooks",
                checked=codex_ok,
                configured=codex_ok,
            ),
        ],
    )

    tmux = SetupGroup(
        "Tmux Bindings",
        [
            SetupItem(
                "switcher",
                "Ctrl+Space",
                "project switcher",
                "Tmux Bindings",
                checked=switcher_ok,
                configured=switcher_ok,
            ),
            SetupItem(
                "notify",
                "Ctrl+N",
                "notification popup",
                "Tmux Bindings",
                checked=notify_ok,
                configured=notify_ok,
            ),
            SetupItem(
                "detach",
                "Ctrl+Q",
                "detach session",
                "Tmux Bindings",
                checked=detach_ok,
                configured=detach_ok,
            ),
        ],
    )

    tools = SetupGroup(
        "Tools",
        [
            SetupItem(
                "terminal-notifier",
                "terminal-notifier",
                "macOS notifications (brew)",
                "Tools",
                checked=tn_ok,
                configured=tn_ok,
            ),
        ],
    )

    return [hooks, tmux, tools]


# ── Rendering ────────────────────────────────────────────────────────────


def _content_row(content: Text, width: int) -> Text:
    plain_len = len(content.plain)
    pad = max(0, width - 4 - plain_len)
    t = Text()
    t.append("│ ", "dim")
    t.append_text(content)
    t.append(" " * pad)
    t.append(" │", "dim")
    return t


def render_setup_panel(
    groups: list[SetupGroup],
    cursor: int,
    width: int,
) -> list[Text]:
    """Render the setup checklist as a bordered panel."""
    w = width
    lines: list[Text] = []

    # ── Top border ──
    title = " kata setup "
    side = (w - 2 - len(title)) // 2
    top = Text()
    top.append("╭", "dim")
    top.append("─" * side, "dim")
    top.append(title, "bold cyan")
    top.append("─" * (w - 2 - side - len(title)), "dim")
    top.append("╮", "dim")
    lines.append(top)

    lines.append(_content_row(Text(""), w))

    # ── Groups & items ──
    flat_idx = 0
    for gi, group in enumerate(groups):
        if gi > 0:
            lines.append(_content_row(Text(""), w))

        # Group header
        header = Text()
        header.append(f"  {group.name}", "bold")
        lines.append(_content_row(header, w))

        for item in group.items:
            is_selected = flat_idx == cursor
            avail = w - 4

            entry = Text()
            if is_selected:
                inner = Text()
                inner.append("┃ ", "cyan")
                check = "✓" if item.checked else " "
                inner.append(f"[{check}]", "bold cyan" if item.checked else "dim")
                inner.append(f" {item.label}", "bold")

                # Status tag
                if item.configured:
                    inner.append("  ✓", "green")

                # Description
                inner.append(f"  {item.description}", "dim")
                fill = max(0, avail - len(inner.plain))
                inner.append(" " * fill)
                inner.stylize("on grey23")
                entry.append_text(inner)
            else:
                check = "✓" if item.checked else " "
                entry.append("  ")
                entry.append(f"[{check}]", "green" if item.checked else "dim")
                entry.append(f" {item.label}")

                if item.configured:
                    entry.append("  ✓", "green")

                entry.append(f"  {item.description}", "dim")

            lines.append(_content_row(entry, w))
            flat_idx += 1

    # ── Spacer ──
    lines.append(_content_row(Text(""), w))

    # ── Separator ──
    sep = Text()
    sep.append("├", "dim")
    sep.append("─" * (w - 2), "dim")
    sep.append("┤", "dim")
    lines.append(sep)

    # ── Hints ──
    hint = Text()
    hint.append(" ␣", "cyan")
    hint.append(" toggle", "dim")
    hint.append("  ↑↓", "cyan")
    hint.append(" move", "dim")
    hint.append("  a", "cyan")
    hint.append(" all", "dim")
    hint.append("  ↵", "cyan")
    hint.append(" apply", "dim")
    hint.append("  esc", "cyan")
    hint.append(" quit", "dim")
    hint_len = len(hint.plain)
    avail = w - 4
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


# ── Input ────────────────────────────────────────────────────────────────


def _read_key(fd: int) -> str:
    """Read a single keypress from a file descriptor already in raw mode."""
    ch = os.read(fd, 1)
    if ch == b"\x00":
        return "ctrl+space"
    elif ch == b"\x1b":
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            seq = os.read(fd, 8)
            if seq == b"[A":
                return "up"
            elif seq == b"[B":
                return "down"
            elif seq == b"[Z":
                return "shift+tab"
            elif seq.startswith(b"O"):
                if seq == b"OA":
                    return "up"
                elif seq == b"OB":
                    return "down"
            return "escape"
        return "escape"
    elif ch in (b"\r", b"\n"):
        return "enter"
    elif ch == b" ":
        return "space"
    elif ch == b"\t":
        return "tab"
    elif ch == b"\x03":
        return "escape"
    elif ch == b"a":
        return "a"
    return ch.decode("utf-8", errors="replace")


# ── Apply logic ──────────────────────────────────────────────────────────


def _apply_selections(groups: list[SetupGroup], console: Console) -> None:
    """Apply selected integrations."""
    selected = {}
    for group in groups:
        for item in group.items:
            selected[item.key] = item.checked

    console.print()
    console.rule("[bold]Applying[/bold]")
    console.print()

    applied = 0

    # Claude Code hooks
    if selected.get("claude"):
        try:
            from kata.services.notifications.hooks.claude_code import (
                setup_hooks as setup_claude,
            )

            setup_claude()
            console.print("[green]✓[/green] Claude Code hooks configured")
            applied += 1
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Claude Code hooks: {e}")

    # Gemini CLI hooks
    if selected.get("gemini"):
        try:
            from kata.services.notifications.hooks.gemini import (
                setup_hooks as setup_gemini,
            )

            setup_gemini()
            console.print("[green]✓[/green] Gemini CLI hooks configured")
            applied += 1
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Gemini CLI hooks: {e}")

    # Codex CLI hooks
    if selected.get("codex"):
        try:
            from kata.services.notifications.hooks.codex import (
                setup_hooks as setup_codex,
            )

            setup_codex()
            console.print("[green]✓[/green] Codex CLI hook configured")
            applied += 1
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Codex CLI hook: {e}")

    # Ctrl+Space switcher
    if selected.get("switcher"):
        tmux_conf = Path.home() / ".tmux.conf"
        marker = "# Kata workspace orchestrator"
        try:
            existing = tmux_conf.read_text() if tmux_conf.exists() else ""
            if "switch-strip" not in existing:
                with tmux_conf.open("a") as f:
                    if marker not in existing:
                        f.write(f"\n{marker}\n")
                    f.write('bind-key -n C-Space run-shell -b "kata switch-strip"\n')
                    f.write(
                        "bind-key -n C-S-Space run-shell -b " '"kata switch-strip --backward"\n'
                    )
            # Apply to current session
            subprocess.run(
                ["tmux", "bind-key", "-n", "C-Space", "run-shell", "-b", "kata switch-strip"],
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            subprocess.run(
                [
                    "tmux",
                    "bind-key",
                    "-n",
                    "C-S-Space",
                    "run-shell",
                    "-b",
                    "kata switch-strip --backward",
                ],
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            console.print("[green]✓[/green] Ctrl+Space / Ctrl+Shift+Space switcher")
            applied += 1
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Switcher binding: {e}")

    # Ctrl+N notification popup
    if selected.get("notify"):
        tmux_conf = Path.home() / ".tmux.conf"
        marker = "# Kata workspace orchestrator"
        try:
            existing = tmux_conf.read_text() if tmux_conf.exists() else ""
            if "notify-popup" not in existing:
                with tmux_conf.open("a") as f:
                    if marker not in existing:
                        f.write(f"\n{marker}\n")
                    f.write('bind-key -n C-n run-shell -b "kata notify-popup"\n')
            subprocess.run(
                ["tmux", "bind-key", "-n", "C-n", "run-shell", "-b", "kata notify-popup"],
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            console.print("[green]✓[/green] Ctrl+N notification popup")
            applied += 1
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Notification binding: {e}")

    # Ctrl+Q detach
    if selected.get("detach"):
        tmux_conf = Path.home() / ".tmux.conf"
        marker = "# Kata workspace orchestrator"
        try:
            existing = tmux_conf.read_text() if tmux_conf.exists() else ""
            if "C-q" not in existing or "detach" not in existing:
                with tmux_conf.open("a") as f:
                    if marker not in existing:
                        f.write(f"\n{marker}\n")
                    f.write("bind-key -n C-q detach-client\n")
            subprocess.run(
                ["tmux", "bind-key", "-n", "C-q", "detach-client"],
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
            console.print("[green]✓[/green] Ctrl+Q detach session")
            applied += 1
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Detach binding: {e}")

    # terminal-notifier
    if selected.get("terminal-notifier"):
        if shutil.which("terminal-notifier"):
            console.print("[dim]terminal-notifier already installed[/dim]")
        elif shutil.which("brew"):
            try:
                console.print("[dim]Installing terminal-notifier via brew...[/dim]")
                result = subprocess.run(
                    ["brew", "install", "terminal-notifier"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    console.print("[green]✓[/green] terminal-notifier installed")
                    applied += 1
                else:
                    console.print(
                        f"[yellow]⚠[/yellow] brew install failed: " f"{result.stderr.strip()}"
                    )
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] terminal-notifier: {e}")
        else:
            console.print(
                "[yellow]⚠[/yellow] Homebrew not found. Install manually: "
                "[bold]brew install terminal-notifier[/bold]"
            )

    console.print()
    if applied:
        console.print(f"[green]✓[/green] Setup complete! ({applied} items applied)")
    else:
        console.print("[dim]Nothing new to apply.[/dim]")


# ── Main ─────────────────────────────────────────────────────────────────


def _calc_panel_size(groups: list[SetupGroup]) -> tuple[int, int]:
    """Calculate panel width and height."""
    # Count rows: top + spacer + (per group: spacer + header + items) + spacer + sep + hint + bottom
    total_items = sum(len(g.items) for g in groups)
    total_groups = len(groups)
    # top(1) + spacer(1) + groups*(header(1)) + group_spacers(groups-1) + items + spacer(1) + sep(1) + hint(1) + bottom(1)
    h = 1 + 1 + total_groups + (total_groups - 1) + total_items + 1 + 1 + 1 + 1

    # Width: widest item content + chrome
    max_content = 0
    for g in groups:
        for item in g.items:
            # "┃ [✓] label  ✓  description"
            line_len = 4 + 3 + 1 + len(item.label) + 4 + len(item.description)
            max_content = max(max_content, line_len)
        # Group header
        max_content = max(max_content, 2 + len(g.name))

    # hint bar width
    hint_w = len(" ␣ toggle  ↑↓ move  a all  ↵ apply  esc quit")
    max_content = max(max_content, hint_w)

    w = max_content + 6  # borders + padding

    return w, h


def run_setup() -> None:
    """Run the interactive setup TUI."""
    console = Console()
    groups = _detect_items()

    # Flatten items for cursor navigation
    flat_items: list[SetupItem] = []
    for g in groups:
        flat_items.extend(g.items)

    if not flat_items:
        console.print("[dim]No integrations available.[/dim]")
        return

    cursor = 0
    confirmed = False
    w, h = _calc_panel_size(groups)

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    # Use a string-buffer console to render Rich Text to ANSI strings
    buf_console = Console(file=StringIO(), force_terminal=True, width=w)

    def _render_frame() -> str:
        """Render panel lines into a single raw-mode-safe string."""
        panel = render_setup_panel(groups, cursor, w)
        buf = buf_console.file
        buf.seek(0)
        buf.truncate()
        for line in panel:
            buf_console.print(line, end="")
            buf.write("\r\n")
        return buf.getvalue()

    try:
        tty.setraw(fd)
        # Hide cursor, clear screen, position at top
        sys.stdout.write("\x1b[?25l\x1b[2J\x1b[H")
        sys.stdout.write(_render_frame())
        sys.stdout.flush()

        while True:
            key = _read_key(fd)

            if key in ("up", "shift+tab"):
                cursor = (cursor - 1) % len(flat_items)
            elif key in ("down", "tab", "ctrl+space"):
                cursor = (cursor + 1) % len(flat_items)
            elif key == "space":
                flat_items[cursor].checked = not flat_items[cursor].checked
            elif key == "a":
                any_unchecked = any(not it.checked for it in flat_items)
                for it in flat_items:
                    it.checked = any_unchecked
            elif key == "enter":
                confirmed = True
                break
            elif key == "escape":
                break
            else:
                continue  # Unknown key, no redraw needed

            # Redraw: move to top-left, overwrite in place
            sys.stdout.write("\x1b[H")
            sys.stdout.write(_render_frame())
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        sys.stdout.write("\x1b[?25h\x1b[2J\x1b[H")  # Show cursor, clear
        sys.stdout.flush()

    if confirmed:
        any_selected = any(it.checked for it in flat_items)
        if any_selected:
            _apply_selections(groups, console)
        else:
            console.print("[dim]Nothing selected. Setup cancelled.[/dim]")
    else:
        console.print("[dim]Setup cancelled.[/dim]")
