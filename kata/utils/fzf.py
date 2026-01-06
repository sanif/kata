"""fzf utilities for interactive project selection."""

import shutil
import subprocess


def is_fzf_available() -> bool:
    """Check if fzf is installed and available.

    Returns:
        True if fzf is installed, False otherwise
    """
    return shutil.which("fzf") is not None


def run_fzf_picker(
    items: list[str],
    preview_cmd: str | None = None,
    header: str | None = None,
    ansi: bool = True,
) -> str | None:
    """Run fzf picker with the given items and return the selected item.

    Args:
        items: List of items to display in fzf
        preview_cmd: Optional preview command (use {} as placeholder for selected item)
        header: Optional header text to display above the list
        ansi: Whether to enable ANSI color support (default True)

    Returns:
        Selected item string, or None if user cancelled (Ctrl-C/Esc)

    Raises:
        RuntimeError: If fzf is not installed
    """
    if not is_fzf_available():
        raise RuntimeError(
            "fzf is not installed. Install it with:\n"
            "  macOS: brew install fzf\n"
            "  Ubuntu: sudo apt install fzf"
        )

    # Build fzf command
    cmd = ["fzf"]

    if ansi:
        cmd.append("--ansi")

    if header:
        cmd.extend(["--header", header])

    if preview_cmd:
        cmd.extend(["--preview", preview_cmd])
        cmd.extend(["--preview-window", "right:50%:wrap"])

    # Join items with newlines for stdin
    input_data = "\n".join(items)

    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
        )

        # fzf returns 0 on selection, 1 on no match, 130 on Ctrl-C/Esc
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    except FileNotFoundError:
        raise RuntimeError("fzf not found in PATH")
    except KeyboardInterrupt:
        return None
