"""Session service for managing tmux sessions."""

import os
import subprocess
from pathlib import Path

from kata.core.config import get_project_config_path, migrate_project_config
from kata.core.models import Project, SessionStatus


class SessionError(Exception):
    """Raised when a session operation fails."""

    pass


class SessionNotFoundError(SessionError):
    """Raised when a session is not found."""

    pass


class ConfigNotFoundError(SessionError):
    """Raised when a config file is not found."""

    pass


def _get_tmux_server() -> "libtmux.Server | None":
    """Get libtmux Server instance if tmux is running.

    Note: libtmux may not work inside Textual TUI due to stdout/stderr
    capture conflicts. Use direct subprocess calls for TUI status queries.

    Returns:
        Server instance or None if tmux not available
    """
    try:
        import libtmux

        server = libtmux.Server()
        # Try to access sessions to verify connection
        _ = server.sessions
        return server
    except Exception:
        return None


def session_exists(session_name: str) -> bool:
    """Check if a tmux session with the given name exists.

    Args:
        session_name: Name of the session to check

    Returns:
        True if session exists, False otherwise
    """
    server = _get_tmux_server()
    if server is None:
        return False

    try:
        return server.has_session(session_name)
    except Exception:
        return False


def get_session_status(session_name: str) -> SessionStatus:
    """Get the status of a tmux session.

    Args:
        session_name: Name of the session

    Returns:
        SessionStatus indicating current state
    """
    server = _get_tmux_server()
    if server is None:
        return SessionStatus.IDLE

    try:
        session = server.sessions.get(session_name=session_name)
        if session is None:
            return SessionStatus.IDLE

        # Check if any client is attached (libtmux uses session_attached)
        attached_count = session.session_attached
        if attached_count and int(attached_count) > 0:
            return SessionStatus.ACTIVE
        return SessionStatus.DETACHED
    except Exception:
        return SessionStatus.IDLE


def get_all_session_statuses() -> dict[str, SessionStatus]:
    """Get status of all tmux sessions in one call.

    Uses direct subprocess call to avoid conflicts with Textual's
    stdout/stderr capture (libtmux doesn't work well inside TUI).

    Returns:
        Dict mapping session name to SessionStatus
    """
    try:
        # Use direct tmux command instead of libtmux to avoid Textual conflicts
        # Format: session_name|attached_count
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}|#{session_attached}"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return {}

        statuses = {}
        for line in result.stdout.strip().split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) >= 2:
                name = parts[0]
                attached = parts[1]
                if attached and int(attached) > 0:
                    statuses[name] = SessionStatus.ACTIVE
                else:
                    statuses[name] = SessionStatus.DETACHED
        return statuses
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return {}


def is_inside_tmux() -> bool:
    """Check if we're running inside a tmux session.

    Returns:
        True if inside tmux, False otherwise
    """
    return bool(os.environ.get("TMUX"))


def launch_session(project: Project) -> None:
    """Launch a new tmux session for a project.

    Uses tmuxp to load the project's YAML config and create the session.

    Args:
        project: Project to launch session for

    Raises:
        ConfigNotFoundError: If the config file doesn't exist
        SessionError: If session creation fails
    """
    # Auto-migrate from legacy location if needed
    migrate_project_config(project.name, project.path)

    config_path = get_project_config_path(project.path)

    if not config_path.exists():
        raise ConfigNotFoundError(f"Config file not found: {config_path}")

    try:
        result = subprocess.run(
            ["tmuxp", "load", "-d", str(config_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise SessionError(f"Failed to launch session: {result.stderr}")
    except FileNotFoundError:
        raise SessionError("tmuxp not found. Please install tmuxp.")


def _get_tmux_client() -> str | None:
    """Get the current tmux client TTY.

    Returns:
        Client TTY path or None if not in tmux
    """
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{client_tty}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def attach_session(session_name: str) -> None:
    """Attach to an existing tmux session.

    Uses context-aware attachment: switch-client if inside tmux,
    attach-session if outside.

    Args:
        session_name: Name of the session to attach to

    Raises:
        SessionNotFoundError: If the session doesn't exist
        SessionError: If attach fails
    """
    if not session_exists(session_name):
        raise SessionNotFoundError(f"Session not found: {session_name}")

    try:
        inside_tmux = is_inside_tmux()

        if inside_tmux:
            # Inside tmux (pane or popup): switch to the target session
            result = subprocess.run(
                ["tmux", "switch-client", "-t", session_name],
            )
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, "switch-client")
        else:
            # Outside tmux: attach to the session (this blocks until detach)
            subprocess.run(
                ["tmux", "attach-session", "-t", session_name],
                check=True,
            )
    except subprocess.CalledProcessError as e:
        raise SessionError(f"Failed to attach to session: {e}")


def kill_session(session_name: str) -> None:
    """Kill a tmux session.

    Args:
        session_name: Name of the session to kill

    Raises:
        SessionNotFoundError: If the session doesn't exist
        SessionError: If kill fails
    """
    if not session_exists(session_name):
        raise SessionNotFoundError(f"Session not found: {session_name}")

    try:
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise SessionError(f"Failed to kill session: {e}")


def launch_or_attach(project: Project) -> None:
    """Launch a session if it doesn't exist, or attach if it does.

    Args:
        project: Project to launch/attach

    Raises:
        SessionError: If operation fails
    """
    import time

    if session_exists(project.name):
        attach_session(project.name)
    else:
        launch_session(project)
        # Wait for session to be ready (tmuxp may take a moment)
        session_ready = False
        for _ in range(20):
            if session_exists(project.name):
                session_ready = True
                break
            time.sleep(0.1)

        if not session_ready:
            raise SessionError(f"Session '{project.name}' failed to start within timeout")

        attach_session(project.name)


def _generate_unique_session_name(base_name: str) -> str:
    """Generate a unique session name by appending a numeric suffix if needed.

    Args:
        base_name: The base session name (typically directory basename)

    Returns:
        A unique session name (base_name or base_name-N)
    """
    # Check if base name is available
    if not session_exists(base_name):
        return base_name

    # Try with numeric suffixes
    for i in range(1, 100):
        candidate = f"{base_name}-{i}"
        if not session_exists(candidate):
            return candidate

    # Fallback: use timestamp
    import time

    return f"{base_name}-{int(time.time())}"


def launch_adhoc_session(directory: str, session_name: str | None = None) -> str:
    """Launch a new tmux session for an unregistered directory.

    Creates an adhoc session using a temporary tmuxp config with a layout
    based on the detected project type.

    Args:
        directory: Path to the directory
        session_name: Optional session name (defaults to directory basename)

    Returns:
        The session name that was created

    Raises:
        SessionError: If session creation fails
    """
    import tempfile

    import yaml

    from kata.core.templates import generate_adhoc_config
    from kata.utils.detection import detect_project_type

    # Resolve the directory path
    directory_path = Path(directory).expanduser().resolve()
    if not directory_path.is_dir():
        raise SessionError(f"Directory not found: {directory}")

    # Determine session name
    base_name = session_name or directory_path.name
    final_name = _generate_unique_session_name(base_name)

    # Detect project type
    project_type = detect_project_type(directory_path)

    # Generate adhoc config
    config = generate_adhoc_config(final_name, str(directory_path), project_type)

    # Write to temporary file and launch
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".yaml",
            prefix="kata-adhoc-",
            delete=False,
        ) as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            temp_path = f.name

        try:
            # Use tmuxp to load the session in detached mode
            result = subprocess.run(
                ["tmuxp", "load", "-d", temp_path],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise SessionError(f"Failed to launch adhoc session: {result.stderr}")

            return final_name
        finally:
            # Clean up temporary config
            Path(temp_path).unlink(missing_ok=True)

    except FileNotFoundError:
        raise SessionError("tmuxp not found. Please install tmuxp.")


def launch_or_attach_adhoc(directory: str) -> None:
    """Attach to an existing session for a directory, or create a new adhoc session.

    Checks if a session with the directory's basename already exists. If so,
    attaches to it. Otherwise, creates a new adhoc session and attaches.

    Args:
        directory: Path to the directory

    Raises:
        SessionError: If operation fails
    """
    import time

    directory_path = Path(directory).expanduser().resolve()
    base_name = directory_path.name

    if session_exists(base_name):
        attach_session(base_name)
    else:
        session_name = launch_adhoc_session(directory)
        # Wait for session to be ready
        session_ready = False
        for _ in range(20):
            if session_exists(session_name):
                session_ready = True
                break
            time.sleep(0.1)

        if not session_ready:
            raise SessionError(f"Session '{session_name}' failed to start within timeout")

        attach_session(session_name)


def get_all_kata_sessions() -> list[str]:
    """Get all tmux sessions that match registered projects.

    Returns:
        List of session names
    """
    server = _get_tmux_server()
    if server is None:
        return []

    try:
        return [s.name for s in server.sessions if s.name]
    except Exception:
        return []


def _parse_command(full_args: str) -> str:
    """Parse full command args to extract meaningful command.

    Examples:
        "node /opt/homebrew/bin/nx run admin-panel:serve" -> "nx run admin-panel:serve"
        "nvim ." -> "nvim"
        "claude" -> "claude"
        "python /path/to/script.py arg1" -> "python script.py arg1"

    Args:
        full_args: Full command line from ps args

    Returns:
        Parsed command suitable for shell_command
    """
    if not full_args:
        return ""

    parts = full_args.split()
    if not parts:
        return ""

    first = parts[0]

    # Handle node-wrapped commands (e.g., nx, npm scripts)
    if first == "node" and len(parts) >= 2:
        script_path = parts[1]
        # Extract script name from path
        script_name = Path(script_path).name
        # Remove .js extension if present
        if script_name.endswith(".js"):
            script_name = script_name[:-3]
        # If it's nx, npx, npm, etc., include remaining args
        if script_name in ("nx", "npx", "npm", "yarn", "pnpm") and len(parts) > 2:
            return f"{script_name} " + " ".join(parts[2:])
        elif script_name in ("nx", "npx", "npm", "yarn", "pnpm"):
            return script_name
        else:
            # For other node scripts, return the script name
            return script_name

    # Handle python-wrapped commands
    if first in ("python", "python3") and len(parts) >= 2:
        script_path = parts[1]
        script_name = Path(script_path).name
        if len(parts) > 2:
            return f"python {script_name} " + " ".join(parts[2:])
        return f"python {script_name}"

    # For other commands, just return the base command name
    return Path(first).name


def get_session_layout(session_name: str) -> dict | None:
    """Capture the current layout of a running tmux session.

    Uses tmux CLI to get:
    - Window names and layouts
    - Pane count and current commands
    - Working directories

    Args:
        session_name: Name of the session to capture

    Returns:
        Dictionary compatible with tmuxp YAML format, or None if capture fails
    """
    from typing import Any

    if not session_exists(session_name):
        return None

    try:
        # Get session start directory
        result = subprocess.run(
            ["tmux", "display-message", "-t", session_name, "-p", "#{session_path}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        start_dir = result.stdout.strip() if result.returncode == 0 else ""

        # Get windows: "index|name|layout"
        result = subprocess.run(
            [
                "tmux",
                "list-windows",
                "-t",
                session_name,
                "-F",
                "#{window_index}|#{window_name}|#{window_layout}",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return None

        windows: list[dict[str, Any]] = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("|")
            if len(parts) < 3:
                continue

            window_index, window_name, window_layout = parts[0], parts[1], parts[2]

            # Get panes for this window (use pane_pid to find actual command)
            panes_result = subprocess.run(
                [
                    "tmux",
                    "list-panes",
                    "-t",
                    f"{session_name}:{window_index}",
                    "-F",
                    "#{pane_pid}|#{pane_current_path}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            panes: list[dict[str, Any]] = []
            if panes_result.returncode == 0:
                # Get all processes with full args for efficiency
                ps_result = subprocess.run(
                    ["ps", "-eo", "pid,ppid,args"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                ps_lines = ps_result.stdout.strip().split("\n") if ps_result.returncode == 0 else []

                for pane_line in panes_result.stdout.strip().split("\n"):
                    if pane_line:
                        pane_parts = pane_line.split("|", 1)
                        pane_pid = pane_parts[0] if pane_parts else ""
                        path = pane_parts[1] if len(pane_parts) > 1 else ""

                        # Find child processes of shell (collect all, pick best)
                        cmd = ""
                        if pane_pid:
                            # Collect all children
                            children = []
                            for ps_line in ps_lines:
                                ps_parts = ps_line.split(None, 2)  # Split into 3 parts max
                                if len(ps_parts) >= 3 and ps_parts[1] == pane_pid:
                                    full_args = ps_parts[2]
                                    parsed = _parse_command(full_args)
                                    children.append(parsed)

                            # Pick best child: prefer non-runtime commands, else last one
                            runtime_cmds = {"node", "python", "python3", "ruby", "perl"}
                            for child in children:
                                base_cmd = child.split()[0] if child else ""
                                if base_cmd and base_cmd not in runtime_cmds:
                                    cmd = child
                                    break
                            # If all are runtimes, use last child (most recent)
                            if not cmd and children:
                                cmd = children[-1]

                        # Skip shells, use actual command
                        shell_cmd = []
                        if cmd and cmd not in ("zsh", "bash", "sh", "fish", "-zsh", "-bash", "-fish"):
                            shell_cmd = [cmd]

                        pane_entry: dict[str, Any] = {"shell_command": shell_cmd}
                        # Add start_directory if different from session start
                        if path and path != start_dir:
                            pane_entry["start_directory"] = path

                        panes.append(pane_entry)

            if not panes:
                panes = [{"shell_command": []}]

            window_entry: dict[str, Any] = {
                "window_name": window_name,
                "panes": panes,
            }

            # Only add layout if it's a recognized preset
            # tmux layouts are complex strings, but we can try to use them
            if window_layout:
                window_entry["layout"] = window_layout

            windows.append(window_entry)

        return {
            "session_name": session_name,
            "start_directory": start_dir,
            "windows": windows,
        }

    except (subprocess.TimeoutExpired, Exception):
        return None


def save_current_session_layout(project: Project) -> Path:
    """Save the current session layout to the project's config file.

    Captures the live tmux session and writes it to the YAML config,
    preserving Kata keybindings (Ctrl+Q, Ctrl+Space).

    Args:
        project: The project whose session to capture

    Returns:
        Path to the saved config file

    Raises:
        SessionError: If capture or writing fails
    """
    import yaml

    from kata.core.templates import _base_template

    if not session_exists(project.name):
        raise SessionError(f"Session not found: {project.name}")

    # Capture current layout
    layout = get_session_layout(project.name)
    if layout is None:
        raise SessionError("Failed to capture session layout")

    # Merge with base template to preserve keybindings
    base = _base_template(project.name, project.path)
    base["windows"] = layout["windows"]
    if layout["start_directory"]:
        base["start_directory"] = layout["start_directory"]

    # Write to config file in project directory
    config_path = get_project_config_path(project.path)

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(base, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    except Exception as e:
        raise SessionError(f"Failed to write config: {e}")

    return config_path
