"""Services module for Kata - registry, session, and routine management."""

from kata.services.registry import (
    DuplicatePathError,
    ProjectNotFoundError,
    Registry,
    get_registry,
)
from kata.services.sessions import (
    ConfigNotFoundError,
    SessionError,
    SessionNotFoundError,
    attach_session,
    get_all_kata_sessions,
    get_session_status,
    is_inside_tmux,
    kill_session,
    launch_or_attach,
    launch_session,
    session_exists,
)
from kata.services.routine import (
    LaunchResult,
    RoutineConfig,
    add_group_to_routine,
    add_project_to_routine,
    clear_routine,
    get_routine_projects,
    launch_group_background,
    launch_projects_background,
    load_routine,
    remove_group_from_routine,
    remove_project_from_routine,
    run_morning_routine,
    save_routine,
)

__all__ = [
    # Registry
    "Registry",
    "get_registry",
    "DuplicatePathError",
    "ProjectNotFoundError",
    # Sessions
    "session_exists",
    "get_session_status",
    "is_inside_tmux",
    "launch_session",
    "attach_session",
    "kill_session",
    "launch_or_attach",
    "get_all_kata_sessions",
    "SessionError",
    "SessionNotFoundError",
    "ConfigNotFoundError",
    # Routine
    "RoutineConfig",
    "LaunchResult",
    "load_routine",
    "save_routine",
    "add_group_to_routine",
    "remove_group_from_routine",
    "add_project_to_routine",
    "remove_project_from_routine",
    "clear_routine",
    "launch_group_background",
    "launch_projects_background",
    "run_morning_routine",
    "get_routine_projects",
]
