"""Interactive TUI for `kata uninstall`.

Mirrors the setup_tui.py pattern: toggleable checklist with arrow/space navigation.
Detects what kata installed and lets the user choose what to remove.
"""

import json
import os
import re
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
class UninstallItem:
    key: str
    label: str
    description: str
    group: str
    checked: bool = False
    found: bool = False


@dataclass
class UninstallGroup:
    name: str
    items: list[UninstallItem] = field(default_factory=list)


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
        content = config_path.read_text()
        return "notify-hook" in content and "kata" in content
    except Exception:
        return False


def _has_tmux_binding(keyword: str) -> bool:
    tmux_conf = Path.home() / ".tmux.conf"
    if not tmux_conf.exists():
        return False
    try:
        return keyword in tmux_conf.read_text()
    except Exception:
        return False


def _count_registered_projects() -> int:
    try:
        from kata.core.config import REGISTRY_FILE

        if not REGISTRY_FILE.exists():
            return 0
        data = json.loads(REGISTRY_FILE.read_text())
        return len(data.get("projects", []))
    except Exception:
        return 0


def _count_project_configs() -> int:
    """Count .kata.yaml files in registered project directories."""
    try:
        from kata.core.config import REGISTRY_FILE

        if not REGISTRY_FILE.exists():
            return 0
        data = json.loads(REGISTRY_FILE.read_text())
        count = 0
        for p in data.get("projects", []):
            path = Path(p.get("path", "")) / ".kata.yaml"
            if path.exists():
                count += 1
        return count
    except Exception:
        return 0


def _is_daemon_running() -> bool:
    try:
        from kata.services.notifications.daemon import is_daemon_running

        return is_daemon_running()
    except Exception:
        return False


def _detect_items() -> list[UninstallGroup]:
    """Detect what kata has installed and build the checklist."""
    claude_path = Path.home() / ".claude" / "settings.json"
    gemini_path = Path.home() / ".gemini" / "settings.json"
    codex_path = Path.home() / ".codex" / "config.toml"

    claude_ok = _has_kata_hooks(claude_path)
    gemini_ok = _has_kata_hooks(gemini_path)
    codex_ok = _has_codex_notify(codex_path)
    switcher_ok = _has_tmux_binding("switch-strip")
    notify_ok = _has_tmux_binding("notify-popup")
    detach_ok = _has_tmux_binding("C-q") and _has_tmux_binding("detach")

    config_dir = Path.home() / ".config" / "kata"
    config_exists = config_dir.exists()
    project_count = _count_registered_projects()
    project_config_count = _count_project_configs()
    daemon_running = _is_daemon_running()

    hooks = UninstallGroup(
        "Hooks",
        [
            UninstallItem(
                "claude",
                "Claude Code hooks",
                "found" if claude_ok else "not configured",
                "Hooks",
                checked=claude_ok,
                found=claude_ok,
            ),
            UninstallItem(
                "gemini",
                "Gemini CLI hooks",
                "found" if gemini_ok else "not configured",
                "Hooks",
                checked=gemini_ok,
                found=gemini_ok,
            ),
            UninstallItem(
                "codex",
                "Codex CLI hooks",
                "found" if codex_ok else "not configured",
                "Hooks",
                checked=codex_ok,
                found=codex_ok,
            ),
        ],
    )

    tmux = UninstallGroup(
        "Tmux Keybindings",
        [
            UninstallItem(
                "switcher",
                "Ctrl+Space switcher",
                "found" if switcher_ok else "not configured",
                "Tmux Keybindings",
                checked=switcher_ok,
                found=switcher_ok,
            ),
            UninstallItem(
                "notify",
                "Ctrl+N notifications",
                "found" if notify_ok else "not configured",
                "Tmux Keybindings",
                checked=notify_ok,
                found=notify_ok,
            ),
            UninstallItem(
                "detach",
                "Ctrl+Q detach",
                "found" if detach_ok else "not configured",
                "Tmux Keybindings",
                checked=detach_ok,
                found=detach_ok,
            ),
        ],
    )

    config_desc = f"{project_count} projects registered" if config_exists else "not found"
    project_desc = f"{project_config_count} files" if project_config_count > 0 else "none found"
    daemon_desc = "running" if daemon_running else "not running"

    data = UninstallGroup(
        "Data",
        [
            UninstallItem(
                "daemon",
                "Notification daemon",
                daemon_desc,
                "Data",
                checked=daemon_running,
                found=daemon_running,
            ),
            UninstallItem(
                "config",
                "Config directory",
                f"~/.config/kata — {config_desc}",
                "Data",
                checked=config_exists,
                found=config_exists,
            ),
            UninstallItem(
                "project_configs",
                "Project .kata.yaml files",
                project_desc,
                "Data",
                checked=False,  # Off by default — user may want to keep
                found=project_config_count > 0,
            ),
        ],
    )

    package = UninstallGroup(
        "Package",
        [
            UninstallItem(
                "package",
                "Uninstall kata package",
                "pipx/pip",
                "Package",
                checked=True,
                found=True,
            ),
        ],
    )

    return [hooks, tmux, data, package]


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


def render_uninstall_panel(
    groups: list[UninstallGroup],
    cursor: int,
    width: int,
) -> list[Text]:
    """Render the uninstall checklist as a bordered panel."""
    w = width
    lines: list[Text] = []

    # ── Top border ──
    title = " kata uninstall "
    side = (w - 2 - len(title)) // 2
    top = Text()
    top.append("╭", "dim")
    top.append("─" * side, "dim")
    top.append(title, "bold red")
    top.append("─" * (w - 2 - side - len(title)), "dim")
    top.append("╮", "dim")
    lines.append(top)

    lines.append(_content_row(Text(""), w))

    # ── Groups & items ──
    flat_idx = 0
    for gi, group in enumerate(groups):
        if gi > 0:
            lines.append(_content_row(Text(""), w))

        header = Text()
        header.append(f"  {group.name}", "bold")
        lines.append(_content_row(header, w))

        for item in group.items:
            is_selected = flat_idx == cursor
            avail = w - 4

            entry = Text()
            if is_selected:
                inner = Text()
                inner.append("┃ ", "red")
                check = "✓" if item.checked else " "
                inner.append(f"[{check}]", "bold red" if item.checked else "dim")
                inner.append(f" {item.label}", "bold")

                if item.found:
                    inner.append("  ●", "green")
                else:
                    inner.append("  ○", "dim")

                inner.append(f"  {item.description}", "dim")
                fill = max(0, avail - len(inner.plain))
                inner.append(" " * fill)
                inner.stylize("on grey23")
                entry.append_text(inner)
            else:
                check = "✓" if item.checked else " "
                entry.append("  ")
                entry.append(f"[{check}]", "red" if item.checked else "dim")
                entry.append(f" {item.label}")

                if item.found:
                    entry.append("  ●", "green")
                else:
                    entry.append("  ○", "dim")

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
    hint.append(" ␣", "red")
    hint.append(" toggle", "dim")
    hint.append("  ↑↓", "red")
    hint.append(" move", "dim")
    hint.append("  a", "red")
    hint.append(" all", "dim")
    hint.append("  ↵", "red")
    hint.append(" confirm", "dim")
    hint.append("  esc", "red")
    hint.append(" cancel", "dim")
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
    if ch == b"\x1b":
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            seq = os.read(fd, 8)
            if seq in (b"[A", b"OA"):
                return "up"
            elif seq in (b"[B", b"OB"):
                return "down"
            return "escape"
        return "escape"
    elif ch in (b"\r", b"\n"):
        return "enter"
    elif ch == b" ":
        return "space"
    elif ch == b"\x03":
        return "escape"
    elif ch == b"a":
        return "a"
    return ch.decode("utf-8", errors="replace")


# ── Removal logic ────────────────────────────────────────────────────────


def _remove_kata_hooks_from_json(settings_path: Path) -> bool:
    """Remove kata hook entries from a JSON settings file."""
    if not settings_path.exists():
        return False
    try:
        data = json.loads(settings_path.read_text())
        hooks = data.get("hooks", {})
        changed = False
        for event_type in list(hooks.keys()):
            original = hooks[event_type]
            filtered = [
                entry
                for entry in original
                if not any("kata notify" in h.get("command", "") for h in entry.get("hooks", []))
            ]
            if len(filtered) != len(original):
                hooks[event_type] = filtered
                changed = True
            # Remove empty event types
            if not hooks[event_type]:
                del hooks[event_type]

        if changed:
            if not hooks:
                data.pop("hooks", None)
            settings_path.write_text(json.dumps(data, indent=2) + "\n")
        return changed
    except Exception:
        return False


def _remove_codex_hooks(config_path: Path) -> bool:
    """Remove kata notify line from codex config.toml."""
    if not config_path.exists():
        return False
    try:
        text = config_path.read_text()
        # Remove the notify line
        new_text = re.sub(r"^notify\s*=\s*\[.*kata.*\]\s*\n?", "", text, flags=re.MULTILINE)
        if new_text != text:
            config_path.write_text(new_text)
            return True
        return False
    except Exception:
        return False


def _remove_tmux_lines(keywords: list[str]) -> bool:
    """Remove lines containing any of the keywords from ~/.tmux.conf."""
    tmux_conf = Path.home() / ".tmux.conf"
    if not tmux_conf.exists():
        return False
    try:
        lines = tmux_conf.read_text().splitlines(keepends=True)
        filtered = [line for line in lines if not any(kw in line for kw in keywords)]

        # Also remove orphaned marker lines (marker with no kata lines following)
        marker = "# Kata workspace orchestrator"
        cleaned: list[str] = []
        for i, line in enumerate(filtered):
            if marker in line:
                # Check if any remaining lines reference kata
                remaining = filtered[i + 1 :]
                has_kata = any("kata" in r for r in remaining)
                if not has_kata:
                    continue  # Drop orphaned marker
            cleaned.append(line)

        # Remove trailing blank lines
        content = "".join(cleaned).rstrip("\n")
        if content:
            content += "\n"

        if len(cleaned) != len(lines):
            tmux_conf.write_text(content)
            return True
        return False
    except Exception:
        return False


def _unbind_tmux_key(key: str) -> None:
    """Unbind a tmux key in the current session."""
    try:
        subprocess.run(
            ["tmux", "unbind-key", "-n", key],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except Exception:
        pass


def _stop_daemon() -> bool:
    """Stop the notification daemon if running."""
    try:
        from kata.services.notifications.daemon import stop_daemon

        return stop_daemon()
    except Exception:
        return False


def _remove_config_dir() -> bool:
    """Remove ~/.config/kata directory."""
    config_dir = Path.home() / ".config" / "kata"
    if config_dir.exists():
        shutil.rmtree(config_dir)
        return True
    return False


def _remove_project_configs() -> int:
    """Remove .kata.yaml files from registered project directories."""
    try:
        from kata.core.config import REGISTRY_FILE

        if not REGISTRY_FILE.exists():
            return 0
        data = json.loads(REGISTRY_FILE.read_text())
        removed = 0
        for p in data.get("projects", []):
            path = Path(p.get("path", "")) / ".kata.yaml"
            if path.exists():
                path.unlink()
                removed += 1
        return removed
    except Exception:
        return 0


def _uninstall_package() -> bool:
    """Uninstall kata package via pipx or pip."""
    # Try pipx first
    try:
        result = subprocess.run(
            ["pipx", "uninstall", "kata-workspace"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try pip
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "kata-workspace"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _apply_removals(groups: list[UninstallGroup], console: Console) -> None:
    """Apply selected removals."""
    selected = {}
    for group in groups:
        for item in group.items:
            selected[item.key] = item.checked

    console.print()
    console.rule("[bold red]Removing[/bold red]")
    console.print()

    removed = 0

    # ── Hooks ──
    if selected.get("claude"):
        path = Path.home() / ".claude" / "settings.json"
        if _remove_kata_hooks_from_json(path):
            console.print("[red]✗[/red] Removed Claude Code hooks")
            removed += 1
        else:
            console.print("[dim]  Claude Code hooks — nothing to remove[/dim]")

    if selected.get("gemini"):
        path = Path.home() / ".gemini" / "settings.json"
        if _remove_kata_hooks_from_json(path):
            console.print("[red]✗[/red] Removed Gemini CLI hooks")
            removed += 1
        else:
            console.print("[dim]  Gemini CLI hooks — nothing to remove[/dim]")

    if selected.get("codex"):
        path = Path.home() / ".codex" / "config.toml"
        if _remove_codex_hooks(path):
            console.print("[red]✗[/red] Removed Codex CLI hooks")
            removed += 1
        else:
            console.print("[dim]  Codex CLI hooks — nothing to remove[/dim]")

    # ── Tmux keybindings ──
    tmux_keywords: list[str] = []
    if selected.get("switcher"):
        tmux_keywords.extend(["switch-strip", "C-Space", "C-S-Space"])
        _unbind_tmux_key("C-Space")
        _unbind_tmux_key("C-S-Space")
    if selected.get("notify"):
        tmux_keywords.extend(["notify-popup"])
        _unbind_tmux_key("C-n")
    if selected.get("detach"):
        tmux_keywords.append("C-q")
        _unbind_tmux_key("C-q")

    if tmux_keywords:
        if _remove_tmux_lines(tmux_keywords):
            console.print("[red]✗[/red] Removed tmux keybindings from ~/.tmux.conf")
            removed += 1
        else:
            console.print("[dim]  Tmux keybindings — nothing to remove[/dim]")

    # ── Data ──
    if selected.get("daemon"):
        if _stop_daemon():
            console.print("[red]✗[/red] Stopped notification daemon")
            removed += 1
        else:
            console.print("[dim]  Notification daemon — not running[/dim]")

    if selected.get("project_configs"):
        count = _remove_project_configs()
        if count:
            console.print(f"[red]✗[/red] Removed {count} .kata.yaml project config(s)")
            removed += 1
        else:
            console.print("[dim]  Project configs — none found[/dim]")

    if selected.get("config"):
        if _remove_config_dir():
            console.print("[red]✗[/red] Removed ~/.config/kata")
            removed += 1
        else:
            console.print("[dim]  Config directory — not found[/dim]")

    # ── Package (always last) ──
    if selected.get("package"):
        console.print("[dim]  Uninstalling kata package...[/dim]")
        if _uninstall_package():
            console.print("[red]✗[/red] Uninstalled kata package")
            removed += 1
        else:
            console.print("[yellow]⚠[/yellow] Could not uninstall package automatically")
            console.print("  Try manually: [bold]pipx uninstall kata-workspace[/bold]")

    console.print()
    if removed:
        console.print(f"[red]✗[/red] Uninstall complete ({removed} items removed)")
    else:
        console.print("[dim]Nothing removed.[/dim]")


# ── Main ─────────────────────────────────────────────────────────────────


def _calc_panel_size(groups: list[UninstallGroup]) -> tuple[int, int]:
    """Calculate panel width and height."""
    total_items = sum(len(g.items) for g in groups)
    total_groups = len(groups)
    h = 1 + 1 + total_groups + (total_groups - 1) + total_items + 1 + 1 + 1 + 1

    max_content = 0
    for g in groups:
        for item in g.items:
            line_len = 4 + 3 + 1 + len(item.label) + 4 + len(item.description)
            max_content = max(max_content, line_len)
        max_content = max(max_content, 2 + len(g.name))

    hint_w = len(" ␣ toggle  ↑↓ move  a all  ↵ confirm  esc cancel")
    max_content = max(max_content, hint_w)
    w = max_content + 6

    return w, h


def run_uninstall() -> None:
    """Run the interactive uninstall TUI."""
    console = Console()
    groups = _detect_items()

    flat_items: list[UninstallItem] = []
    for g in groups:
        flat_items.extend(g.items)

    if not flat_items:
        console.print("[dim]Nothing to uninstall.[/dim]")
        return

    cursor = 0
    confirmed = False
    w, h = _calc_panel_size(groups)

    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    buf_console = Console(file=StringIO(), force_terminal=True, width=w)

    def _render_frame() -> str:
        panel = render_uninstall_panel(groups, cursor, w)
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
        sys.stdout.write(_render_frame())
        sys.stdout.flush()

        while True:
            key = _read_key(fd)

            if key == "up":
                cursor = (cursor - 1) % len(flat_items)
            elif key == "down":
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
                continue

            sys.stdout.write("\x1b[H")
            sys.stdout.write(_render_frame())
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        sys.stdout.write("\x1b[?25h\x1b[2J\x1b[H")
        sys.stdout.flush()

    if confirmed:
        any_selected = any(it.checked for it in flat_items)
        if any_selected:
            _apply_removals(groups, console)
        else:
            console.print("[dim]Nothing selected. Uninstall cancelled.[/dim]")
    else:
        console.print("[dim]Uninstall cancelled.[/dim]")
