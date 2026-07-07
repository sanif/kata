"""Interactive TUI for `kata setup`.

Shows all integrations as a toggleable checklist with arrow/space navigation.
"""

import shutil
import subprocess
from dataclasses import dataclass, field
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
from kata.cli._tmux_bindings import BINDING_LINES, install_tmux_lines
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


def _has_tmux_worktree() -> bool:
    tmux_conf = Path.home() / ".tmux.conf"
    if not tmux_conf.exists():
        return False
    try:
        return "worktree-strip" in tmux_conf.read_text()
    except Exception:
        return False


def _detect_items() -> list[SetupGroup]:
    """Detect current state and build the item list."""
    claude_settings = Path.home() / ".claude" / "settings.json"
    gemini_settings = Path.home() / ".gemini" / "settings.json"
    codex_settings = Path.home() / ".codex" / "config.toml"

    claude_ok = has_kata_hooks(claude_settings)
    gemini_ok = has_kata_hooks(gemini_settings)
    codex_ok = _has_codex_notify(codex_settings)
    tn_ok = shutil.which("terminal-notifier") is not None
    switcher_ok = _has_tmux_switcher()
    notify_ok = _has_tmux_notify()
    detach_ok = _has_tmux_detach()
    worktree_ok = _has_tmux_worktree()

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
                "project switcher (overrides C-Space editor set-mark)",
                "Tmux Bindings",
                checked=switcher_ok,
                configured=switcher_ok,
            ),
            SetupItem(
                "notify",
                "Ctrl+N",
                "notification popup (overrides C-n readline history / next-line)",
                "Tmux Bindings",
                checked=notify_ok,
                configured=notify_ok,
            ),
            SetupItem(
                "detach",
                "Ctrl+Q",
                "detach session (overrides C-q terminal resume / XON)",
                "Tmux Bindings",
                checked=detach_ok,
                configured=detach_ok,
            ),
            SetupItem(
                "worktree",
                "Ctrl+W",
                "worktree manager (overrides C-w readline delete-word)",
                "Tmux Bindings",
                checked=worktree_ok,
                configured=worktree_ok,
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

    lines.append(content_row(Text(""), w))

    # ── Groups & items ──
    flat_idx = 0
    for gi, group in enumerate(groups):
        if gi > 0:
            lines.append(content_row(Text(""), w))

        # Group header
        header = Text()
        header.append(f"  {group.name}", "bold")
        lines.append(content_row(header, w))

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
    lines.append(content_row(centered, w))

    # ── Bottom border ──
    bot = Text()
    bot.append("╰", "dim")
    bot.append("─" * (w - 2), "dim")
    bot.append("╯", "dim")
    lines.append(bot)

    return lines


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

            status = setup_codex()
            if status == "existing_notify_preserved":
                console.print(
                    "[yellow]⚠[/yellow] Codex CLI: your existing [bold]notify[/bold] "
                    "command was preserved — kata was NOT installed over it. "
                    "Remove it from ~/.codex/config.toml first to enable kata notifications."
                )
            elif status == "already_installed":
                console.print("[dim]  Codex CLI hook — already configured[/dim]")
            else:
                console.print("[green]✓[/green] Codex CLI hook configured")
            applied += 1
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Codex CLI hook: {e}")

    # ── Tmux keybindings ──
    # Live-apply commands per binding key (argv lists for the current session).
    live_binds: dict[str, list[list[str]]] = {
        "switcher": [
            ["tmux", "bind-key", "-n", "C-Space", "run-shell", "-b", "kata switch-strip"],
            [
                "tmux",
                "bind-key",
                "-n",
                "C-S-Space",
                "run-shell",
                "-b",
                "kata switch-strip --backward",
            ],
        ],
        "notify": [
            ["tmux", "bind-key", "-n", "C-n", "run-shell", "-b", "kata notify-popup"],
        ],
        "detach": [
            ["tmux", "bind-key", "-n", "C-q", "detach-client"],
        ],
        "worktree": [
            ["tmux", "bind-key", "-n", "C-w", "run-shell", "-b", "kata worktree-strip"],
        ],
    }
    bind_labels = {
        "switcher": "Ctrl+Space / Ctrl+Shift+Space switcher",
        "notify": "Ctrl+N notification popup",
        "detach": "Ctrl+Q detach session",
        "worktree": "Ctrl+W worktree manager",
    }

    conf_lines_to_add: list[str] = []
    for key in ("switcher", "notify", "detach", "worktree"):
        if not selected.get(key):
            continue
        try:
            conf_lines_to_add.extend(BINDING_LINES[key])
            for argv in live_binds[key]:
                subprocess.run(argv, capture_output=True, timeout=SUBPROCESS_TIMEOUT)
            console.print(f"[green]✓[/green] {bind_labels[key]}")
            applied += 1
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] {bind_labels[key]}: {e}")

    if conf_lines_to_add:
        try:
            install_tmux_lines(conf_lines_to_add)
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Writing ~/.tmux.conf: {e}")

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
                        f"[yellow]⚠[/yellow] brew install failed: {result.stderr.strip()}"
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
    import sys

    guard_tty()
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

    renderer = FrameRenderer(w)

    def _render_frame() -> str:
        return renderer.render(render_setup_panel(groups, cursor, w))

    with raw_screen() as fd:
        sys.stdout.write(_render_frame())
        sys.stdout.flush()

        while True:
            key = read_key(fd)

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

    if confirmed:
        any_selected = any(it.checked for it in flat_items)
        if any_selected:
            _apply_selections(groups, console)
        else:
            console.print("[dim]Nothing selected. Setup cancelled.[/dim]")
    else:
        console.print("[dim]Setup cancelled.[/dim]")
