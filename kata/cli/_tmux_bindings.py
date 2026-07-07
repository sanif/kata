"""Canonical tmux keybinding lines kata writes to ``~/.tmux.conf``.

Shared by ``setup_tui`` (which installs them, fenced) and ``uninstall_tui``
(which removes them by exact match). Keeping the exact strings in one place is
what lets the uninstaller remove precisely what setup wrote — and nothing a
user added themselves (e.g. their own ``bind-key -n C-q send-prefix``).
"""

from __future__ import annotations

from pathlib import Path

# Fence markers wrapping kata's block in ~/.tmux.conf (current installs).
FENCE_START = "# >>> kata keybindings >>>"
FENCE_END = "# <<< kata keybindings <<<"

# Legacy marker used before the fence existed (still removed on uninstall).
LEGACY_MARKER = "# Kata workspace orchestrator"

# key -> exact config line(s) setup writes for that binding.
BINDING_LINES: dict[str, list[str]] = {
    "switcher": [
        'bind-key -n C-Space run-shell -b "kata switch-strip"',
        'bind-key -n C-S-Space run-shell -b "kata switch-strip --backward"',
    ],
    "notify": [
        'bind-key -n C-n run-shell -b "kata notify-popup"',
    ],
    "detach": [
        "bind-key -n C-q detach-client",
    ],
    "worktree": [
        'bind-key -n C-w run-shell -b "kata worktree-strip"',
    ],
}


def all_binding_lines() -> set[str]:
    """Every exact line kata's setup may write, across all bindings."""
    return {line for lines in BINDING_LINES.values() for line in lines}


def tmux_conf_path() -> Path:
    return Path.home() / ".tmux.conf"


def install_tmux_lines(new_lines: list[str]) -> None:
    """Add ``new_lines`` to ~/.tmux.conf inside kata's fenced block.

    Idempotent: lines already present anywhere in the file are skipped, and an
    existing fenced block is extended in place rather than duplicated.
    """
    conf = tmux_conf_path()
    text = conf.read_text() if conf.exists() else ""
    lines = text.splitlines()

    already = set(lines)
    to_add = [ln for ln in new_lines if ln not in already]
    if not to_add:
        return

    if FENCE_START in lines and FENCE_END in lines:
        start = lines.index(FENCE_START)
        end = lines.index(FENCE_END)
        block = lines[start + 1 : end]
        for ln in to_add:
            if ln not in block:
                block.append(ln)
        merged = lines[: start + 1] + block + lines[end:]
        conf.write_text("\n".join(merged) + "\n")
    else:
        prefix = text.rstrip("\n")
        if prefix:
            prefix += "\n\n"
        block = [FENCE_START, *to_add, FENCE_END]
        conf.write_text(prefix + "\n".join(block) + "\n")
