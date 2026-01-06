"""Session service for managing tmux sessions."""

import os
import subprocess
from pathlib import Path

from kata.core.config import CONFIGS_DIR
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

    Returns:
        Server instance or None if tmux not available
    """
    try:
        import libtmux

        return libtmux.Server()
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
    config_path = CONFIGS_DIR / project.config

    if not config_path.exists():
        raise ConfigNotFoundError(f"Config file not found: {config_path}")

    try:
        # Use tmuxp to load the session in detached mode
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
        # Try to get client TTY (works even in popups)
        client_tty = _get_tmux_client()

        if client_tty or is_inside_tmux():
            # Inside tmux (or popup): switch to the target session
            cmd = ["tmux", "switch-client", "-t", session_name]
            if client_tty:
                # Explicit client needed for popups
                cmd.extend(["-c", client_tty])
            subprocess.run(cmd, check=True)
        else:
            # Outside tmux: attach to the session
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
        for _ in range(10):
            if session_exists(project.name):
                break
            time.sleep(0.1)
        attach_session(project.name)


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
