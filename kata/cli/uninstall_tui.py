"""Interactive TUI for `kata uninstall`.

Mirrors the setup_tui.py pattern: toggleable checklist with arrow/space navigation.
Detects what kata installed and lets the user choose what to remove.
"""

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.text import Text

from kata.cli._termui import (
    FrameRenderer,
    content_row,
    guard_tty,
    has_kata_hooks,
    raw_screen,
    read_key,
)
from kata.cli._tmux_bindings import (
    BINDING_LINES,
    FENCE_END,
    FENCE_START,
    LEGACY_MARKER,
    tmux_conf_path,
)
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

    claude_ok = has_kata_hooks(claude_path)
    gemini_ok = has_kata_hooks(gemini_path)
    codex_ok = _has_codex_notify(codex_path)
    switcher_ok = _has_tmux_binding("switch-strip")
    notify_ok = _has_tmux_binding("notify-popup")
    detach_ok = _has_tmux_binding("C-q") and _has_tmux_binding("detach")
    worktree_ok = _has_tmux_binding("worktree-strip")

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
            UninstallItem(
                "worktree",
                "Ctrl+W worktree manager",
                "found" if worktree_ok else "not configured",
                "Tmux Keybindings",
                checked=worktree_ok,
                found=worktree_ok,
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

    lines.append(content_row(Text(""), w))

    # ── Groups & items ──
    flat_idx = 0
    for gi, group in enumerate(groups):
        if gi > 0:
            lines.append(content_row(Text(""), w))

        header = Text()
        header.append(f"  {group.name}", "bold")
        lines.append(content_row(header, w))

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

            lines.append(content_row(entry, w))
            flat_idx += 1

    # ── Spacer ──
    lines.append(content_row(Text(""), w))

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
    lines.append(content_row(centered, w))

    # ── Bottom border ──
    bot = Text()
    bot.append("╰", "dim")
    bot.append("─" * (w - 2), "dim")
    bot.append("╯", "dim")
    lines.append(bot)

    return lines


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


def _backup_tmux_conf(original: str) -> Path | None:
    """Write a timestamped backup of ~/.tmux.conf before we modify it."""
    conf = tmux_conf_path()
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = conf.with_name(f"{conf.name}.kata-backup-{ts}")
    try:
        backup.write_text(original)
        return backup
    except Exception:
        return None


def _strip_empty_fence(lines: list[str]) -> list[str]:
    """Drop kata's fence markers when the block between them is empty."""
    if FENCE_START not in lines or FENCE_END not in lines:
        return lines
    start = lines.index(FENCE_START)
    # Find the matching end after start.
    try:
        end = lines.index(FENCE_END, start + 1)
    except ValueError:
        return lines
    inner = lines[start + 1 : end]
    if all(not ln.strip() for ln in inner):
        return lines[:start] + lines[end + 1 :]
    return lines


def _strip_orphan_legacy_marker(lines: list[str]) -> list[str]:
    """Drop a legacy kata marker that no longer precedes any kata line."""
    cleaned: list[str] = []
    for i, line in enumerate(lines):
        if LEGACY_MARKER in line:
            if not any("kata" in r for r in lines[i + 1 :]):
                continue
        cleaned.append(line)
    return cleaned


def _remove_tmux_bindings(keys: list[str]) -> tuple[bool, Path | None]:
    """Remove kata's exact keybinding lines for ``keys`` from ~/.tmux.conf.

    Only lines that *exactly* match what kata's setup writes are removed, so a
    user's own bindings on the same keys (e.g. ``bind-key C-q send-prefix``)
    survive. Handles both the fenced block (current installs) and legacy
    marker-delimited lines. Writes a timestamped backup before any change.

    Returns ``(changed, backup_path)``.
    """
    conf = tmux_conf_path()
    if not conf.exists():
        return False, None
    try:
        original = conf.read_text()
    except Exception:
        return False, None

    lines = original.splitlines()
    remove_exact = {ln.strip() for k in keys for ln in BINDING_LINES.get(k, [])}

    kept = [ln for ln in lines if ln.strip() not in remove_exact]
    kept = _strip_empty_fence(kept)
    kept = _strip_orphan_legacy_marker(kept)

    if kept == lines:
        return False, None

    backup = _backup_tmux_conf(original)
    content = "\n".join(kept).rstrip("\n")
    if content:
        content += "\n"
    try:
        conf.write_text(content)
    except Exception:
        return False, backup
    return True, backup


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


def _remove_config_dir() -> tuple[bool, str | None]:
    """Remove ~/.config/kata directory.

    Returns ``(removed, error)`` — never raises, so a permission error reports
    cleanly instead of tearing down the uninstaller with a traceback.
    """
    config_dir = Path.home() / ".config" / "kata"
    if not config_dir.exists():
        return False, None
    try:
        shutil.rmtree(config_dir)
        return True, None
    except OSError as e:
        return False, str(e)


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
    tmux_keys: list[str] = []
    if selected.get("switcher"):
        tmux_keys.append("switcher")
        _unbind_tmux_key("C-Space")
        _unbind_tmux_key("C-S-Space")
    if selected.get("notify"):
        tmux_keys.append("notify")
        _unbind_tmux_key("C-n")
    if selected.get("detach"):
        tmux_keys.append("detach")
        _unbind_tmux_key("C-q")
    if selected.get("worktree"):
        tmux_keys.append("worktree")
        _unbind_tmux_key("C-w")

    if tmux_keys:
        changed, backup = _remove_tmux_bindings(tmux_keys)
        if changed:
            console.print("[red]✗[/red] Removed tmux keybindings from ~/.tmux.conf")
            if backup:
                console.print(f"[dim]  Backup saved: {backup}[/dim]")
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
        ok, error = _remove_config_dir()
        if ok:
            console.print("[red]✗[/red] Removed ~/.config/kata")
            removed += 1
        elif error:
            console.print(f"[yellow]⚠[/yellow] Could not remove ~/.config/kata: {error}")
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
    guard_tty()
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

    renderer = FrameRenderer(w)

    def _render_frame() -> str:
        return renderer.render(render_uninstall_panel(groups, cursor, w))

    with raw_screen() as fd:
        sys.stdout.write(_render_frame())
        sys.stdout.flush()

        while True:
            key = read_key(fd)

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

    if confirmed:
        any_selected = any(it.checked for it in flat_items)
        if any_selected:
            _apply_removals(groups, console)
        else:
            console.print("[dim]Nothing selected. Uninstall cancelled.[/dim]")
    else:
        console.print("[dim]Uninstall cancelled.[/dim]")
