"""CLI application for Kata."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from kata.core.models import Project
from kata.core.templates import get_template_path, write_template
from kata.services.registry import (
    DuplicatePathError,
    ProjectNotFoundError,
    get_registry,
)
from kata.services.sessions import (
    SessionError,
    SessionNotFoundError,
    get_all_kata_sessions,
    get_all_session_statuses,
    get_session_status,
    kill_session,
    launch_or_attach,
    session_exists,
)
from kata.utils.detection import detect_project_type
from kata.utils.paths import PathValidationError, validate_project_path

app = typer.Typer(
    name="kata",
    help="Terminal-centric workspace orchestrator for tmux",
    no_args_is_help=False,
)
console = Console()


def _status_indicator(status: str) -> str:
    """Get status indicator with color."""
    indicators = {
        "active": "[green]●[/green] Active",
        "detached": "[yellow]●[/yellow] Detached",
        "idle": "[dim]●[/dim] Idle",
    }
    return indicators.get(status, "[dim]●[/dim] Unknown")


@app.command()
def add(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to the project directory (defaults to current directory)",
    ),
    group: str = typer.Option(
        "Uncategorized",
        "--group",
        "-g",
        help="Group to add the project to",
    ),
) -> None:
    """Add a project to Kata."""
    # Use current directory if no path provided
    project_path = path or Path.cwd()

    try:
        validated_path = validate_project_path(project_path)
    except PathValidationError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Detect project type
    project_type = detect_project_type(validated_path)

    # Create project
    project = Project.from_path(validated_path, group=group)

    # Add to registry
    registry = get_registry()
    try:
        registry.add(project)
    except DuplicatePathError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    # Generate template
    config_path = write_template(project, project_type)

    console.print(f"[green]✓[/green] Added project: [bold]{project.name}[/bold]")
    console.print(f"  Path: {project.path}")
    console.print(f"  Type: {project_type.value}")
    console.print(f"  Group: {project.group}")
    console.print(f"  Config: {config_path}")


@app.command("list")
def list_projects(
    group: Optional[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Filter by group",
    ),
) -> None:
    """List all registered projects."""
    registry = get_registry()

    if group:
        projects = registry.list_by_group(group)
    else:
        projects = registry.list_all()

    if not projects:
        console.print("[dim]No projects registered yet.[/dim]")
        console.print("Use [bold]kata add[/bold] to add a project.")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Status", width=12)
    table.add_column("Name", style="cyan")
    table.add_column("Group", style="magenta")
    table.add_column("Path", style="dim")

    for project in sorted(projects, key=lambda p: (p.group, p.name)):
        status = get_session_status(project.name)
        table.add_row(
            _status_indicator(status.value),
            project.name,
            project.group,
            project.path,
        )

    console.print(table)


@app.command()
def remove(
    name: str = typer.Argument(..., help="Name of the project to remove"),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation",
    ),
) -> None:
    """Remove a project from Kata."""
    registry = get_registry()

    try:
        project = registry.get(name)
    except ProjectNotFoundError:
        console.print(f"[red]Error:[/red] Project not found: {name}")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Remove project '{project.name}'?")
        if not confirm:
            console.print("Cancelled.")
            raise typer.Exit(0)

    registry.remove(name)
    console.print(f"[green]✓[/green] Removed project: [bold]{name}[/bold]")


@app.command()
def launch(
    name: str = typer.Argument(..., help="Name of the project to launch"),
) -> None:
    """Launch or attach to a project's tmux session."""
    registry = get_registry()

    try:
        project = registry.get(name)
    except ProjectNotFoundError:
        console.print(f"[red]Error:[/red] Project not found: {name}")
        raise typer.Exit(1)

    try:
        # Record that we opened this project
        project.record_open()
        registry.update(project)

        launch_or_attach(project)
    except SessionError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def kill(
    name: Optional[str] = typer.Argument(
        None,
        help="Name of the session to kill",
    ),
    all_sessions: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Kill all Kata-managed sessions",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Kill tmux session(s).

    Kill a specific session by name, or use --all to kill all Kata-managed sessions.
    """
    registry = get_registry()

    if all_sessions:
        # Get all sessions that correspond to registered projects
        registered_names = {p.name for p in registry.list_all()}
        active_sessions = [
            name for name in get_all_kata_sessions() if name in registered_names
        ]

        if not active_sessions:
            console.print("[dim]No active Kata sessions to kill.[/dim]")
            return

        console.print(f"Found {len(active_sessions)} active session(s):")
        for session_name in active_sessions:
            status = get_session_status(session_name)
            console.print(f"  {_status_indicator(status.value)} {session_name}")

        if not force:
            confirm = typer.confirm("\nKill all these sessions?")
            if not confirm:
                console.print("Cancelled.")
                raise typer.Exit(0)

        killed = 0
        for session_name in active_sessions:
            try:
                kill_session(session_name)
                console.print(f"[green]✓[/green] Killed: {session_name}")
                killed += 1
            except SessionError as e:
                console.print(f"[red]✗[/red] Failed to kill {session_name}: {e}")

        console.print(f"\n[green]Killed {killed} session(s).[/green]")
    else:
        if not name:
            console.print("[red]Error:[/red] Provide a session name or use --all")
            raise typer.Exit(1)

        # Check if it's a registered project
        if name not in registry:
            console.print(f"[yellow]Warning:[/yellow] '{name}' is not a registered project")

        if not session_exists(name):
            console.print(f"[red]Error:[/red] No active session found: {name}")
            raise typer.Exit(1)

        if not force:
            confirm = typer.confirm(f"Kill session '{name}'?")
            if not confirm:
                console.print("Cancelled.")
                raise typer.Exit(0)

        try:
            kill_session(name)
            console.print(f"[green]✓[/green] Killed session: [bold]{name}[/bold]")
        except SessionError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)


@app.command()
def scan(
    path: Optional[Path] = typer.Argument(
        None,
        help="Directory to scan (defaults to current directory)",
    ),
    depth: int = typer.Option(
        3,
        "--depth",
        "-d",
        help="Maximum depth to recurse",
    ),
    group: str = typer.Option(
        "Uncategorized",
        "--group",
        "-g",
        help="Group to add discovered projects to",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Auto-import all discovered projects without prompting",
    ),
) -> None:
    """Scan directory for projects and import them.

    Recursively scans for project directories (identified by .git, pyproject.toml,
    package.json, go.mod, etc.) and offers to import them.
    """
    from kata.utils.scanner import get_project_info, scan_directory

    scan_path = (path or Path.cwd()).resolve()

    if not scan_path.is_dir():
        console.print(f"[red]Error:[/red] Not a directory: {scan_path}")
        raise typer.Exit(1)

    console.print(f"Scanning [bold]{scan_path}[/bold] (depth: {depth})...")

    discovered = scan_directory(scan_path, max_depth=depth)

    if not discovered:
        console.print("[dim]No projects found.[/dim]")
        return

    # Filter out already-registered paths
    registry = get_registry()
    new_projects: list[Path] = []
    for project_path in discovered:
        if registry.find_by_path(project_path) is None:
            new_projects.append(project_path)

    if not new_projects:
        console.print(
            f"Found {len(discovered)} project(s), but all are already registered."
        )
        return

    console.print(f"\nFound [bold]{len(new_projects)}[/bold] new project(s):\n")

    # Display projects with info
    project_infos = [get_project_info(p) for p in new_projects]
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", style="dim", width=3)
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Path", style="dim")

    for i, info in enumerate(project_infos, 1):
        table.add_row(
            str(i),
            info["name"],
            info["type"],
            info["path"],
        )

    console.print(table)
    console.print()

    if yes:
        # Auto-import all
        selected_indices = list(range(len(new_projects)))
    else:
        # Interactive selection
        console.print("Enter project numbers to import (comma-separated), 'all', or 'none':")
        selection = typer.prompt("Selection", default="all")

        if selection.lower() == "none":
            console.print("Cancelled.")
            return
        elif selection.lower() == "all":
            selected_indices = list(range(len(new_projects)))
        else:
            try:
                selected_indices = [int(x.strip()) - 1 for x in selection.split(",")]
                # Validate indices
                for idx in selected_indices:
                    if idx < 0 or idx >= len(new_projects):
                        raise ValueError(f"Invalid index: {idx + 1}")
            except ValueError as e:
                console.print(f"[red]Error:[/red] Invalid selection: {e}")
                raise typer.Exit(1)

    # Import selected projects
    imported = 0
    for idx in selected_indices:
        project_path = new_projects[idx]
        try:
            validated_path = validate_project_path(project_path)
            project_type = detect_project_type(validated_path)
            project = Project.from_path(validated_path, group=group)

            registry.add(project)
            write_template(project, project_type)

            console.print(f"[green]✓[/green] Imported: {project.name}")
            imported += 1
        except (PathValidationError, DuplicatePathError) as e:
            console.print(f"[red]✗[/red] Failed to import {project_path.name}: {e}")

    console.print(f"\n[green]Imported {imported} project(s).[/green]")


@app.command()
def move(
    name: str = typer.Argument(..., help="Name of the project to move"),
    group: str = typer.Argument(..., help="Target group name"),
) -> None:
    """Move a project to a different group."""
    registry = get_registry()

    try:
        project = registry.get(name)
    except ProjectNotFoundError:
        console.print(f"[red]Error:[/red] Project not found: {name}")
        raise typer.Exit(1)

    old_group = project.group
    project.group = group
    registry.update(project)

    console.print(
        f"[green]✓[/green] Moved [bold]{name}[/bold] from "
        f"[magenta]{old_group}[/magenta] to [magenta]{group}[/magenta]"
    )


def _get_editor() -> str:
    """Get the editor command with fallback chain.

    Returns:
        Editor command to use
    """
    import os

    # Check environment variables in order of preference
    for env_var in ["EDITOR", "VISUAL"]:
        editor = os.environ.get(env_var)
        if editor:
            return editor

    # Fallback chain for common editors
    import shutil

    for fallback in ["nano", "vim", "vi"]:
        if shutil.which(fallback):
            return fallback

    # Last resort
    return "vi"


@app.command()
def edit(
    name: str = typer.Argument(..., help="Name of the project to edit"),
) -> None:
    """Open a project's tmuxp config in your editor.

    Uses $EDITOR, $VISUAL, or falls back to nano/vim/vi.
    """
    import subprocess

    registry = get_registry()

    try:
        project = registry.get(name)
    except ProjectNotFoundError:
        console.print(f"[red]Error:[/red] Project not found: {name}")
        raise typer.Exit(1)

    config_path = get_template_path(project)

    if not config_path.exists():
        console.print(f"[red]Error:[/red] Config file not found: {config_path}")
        console.print("Run [bold]kata add[/bold] again to regenerate the config.")
        raise typer.Exit(1)

    editor = _get_editor()
    console.print(f"Opening [bold]{config_path}[/bold] with {editor}...")

    try:
        # Run editor synchronously
        result = subprocess.run([editor, str(config_path)])
        if result.returncode != 0:
            console.print(f"[yellow]Warning:[/yellow] Editor exited with code {result.returncode}")
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Editor not found: {editor}")
        console.print("Set $EDITOR environment variable to your preferred editor.")
        raise typer.Exit(1)
    except KeyboardInterrupt:
        console.print("\n[dim]Editing cancelled.[/dim]")


@app.command()
def routine(
    action: str = typer.Argument(
        "run",
        help="Action: run, add, remove, list, clear",
    ),
    target: Optional[str] = typer.Argument(
        None,
        help="Group or project name (for add/remove actions)",
    ),
    project: bool = typer.Option(
        False,
        "--project",
        "-p",
        help="Target is a project name instead of group",
    ),
) -> None:
    """Manage and run the morning routine.

    The morning routine launches multiple projects in background.

    Examples:
        kata routine                   # Run the routine
        kata routine add Work          # Add "Work" group to routine
        kata routine add myproject -p  # Add specific project
        kata routine remove Work       # Remove group from routine
        kata routine list              # Show routine configuration
        kata routine clear             # Clear all routine settings
    """
    from kata.services.routine import (
        add_group_to_routine,
        add_project_to_routine,
        clear_routine,
        get_routine_projects,
        load_routine,
        remove_group_from_routine,
        remove_project_from_routine,
        run_morning_routine,
    )

    if action == "run":
        routine_projects = get_routine_projects()
        if not routine_projects:
            console.print("[yellow]No projects configured in routine.[/yellow]")
            console.print("Use [bold]kata routine add <group>[/bold] to add groups.")
            return

        console.print(f"[bold]Starting morning routine ({len(routine_projects)} projects)...[/bold]\n")

        results = run_morning_routine()

        launched = 0
        skipped = 0
        failed = 0

        for result in results:
            if result.success:
                if result.skipped:
                    console.print(f"  [dim]⏭ {result.project.name} (already running)[/dim]")
                    skipped += 1
                else:
                    console.print(f"  [green]✓[/green] {result.project.name}")
                    launched += 1
            else:
                console.print(f"  [red]✗[/red] {result.project.name}: {result.error}")
                failed += 1

        console.print(f"\n[bold]Done![/bold] Launched: {launched}, Skipped: {skipped}, Failed: {failed}")

    elif action == "add":
        if not target:
            console.print("[red]Error:[/red] Specify a group or project name")
            raise typer.Exit(1)

        if project:
            # Add specific project
            registry = get_registry()
            if target not in registry:
                console.print(f"[red]Error:[/red] Project not found: {target}")
                raise typer.Exit(1)

            if add_project_to_routine(target):
                console.print(f"[green]✓[/green] Added project [bold]{target}[/bold] to routine")
            else:
                console.print(f"[yellow]Already in routine:[/yellow] {target}")
        else:
            # Add group
            registry = get_registry()
            groups = registry.get_groups()
            if target not in groups:
                console.print(f"[yellow]Warning:[/yellow] Group '{target}' doesn't exist yet")

            if add_group_to_routine(target):
                console.print(f"[green]✓[/green] Added group [bold]{target}[/bold] to routine")
            else:
                console.print(f"[yellow]Already in routine:[/yellow] {target}")

    elif action == "remove":
        if not target:
            console.print("[red]Error:[/red] Specify a group or project name")
            raise typer.Exit(1)

        if project:
            if remove_project_from_routine(target):
                console.print(f"[green]✓[/green] Removed project [bold]{target}[/bold] from routine")
            else:
                console.print(f"[dim]Not in routine:[/dim] {target}")
        else:
            if remove_group_from_routine(target):
                console.print(f"[green]✓[/green] Removed group [bold]{target}[/bold] from routine")
            else:
                console.print(f"[dim]Not in routine:[/dim] {target}")

    elif action == "list":
        config = load_routine()

        if not config.groups and not config.projects:
            console.print("[dim]No routine configured.[/dim]")
            console.print("Use [bold]kata routine add <group>[/bold] to add groups.")
            return

        console.print("[bold]Morning Routine Configuration[/bold]\n")

        if config.groups:
            console.print("[cyan]Groups:[/cyan]")
            for group in config.groups:
                projects = get_registry().list_by_group(group)
                console.print(f"  • {group} ({len(projects)} projects)")

        if config.projects:
            console.print("\n[cyan]Individual Projects:[/cyan]")
            for proj in config.projects:
                console.print(f"  • {proj}")

        # Show total
        routine_projects = get_routine_projects()
        console.print(f"\n[dim]Total: {len(routine_projects)} projects will be launched[/dim]")

    elif action == "clear":
        confirm = typer.confirm("Clear all routine settings?")
        if not confirm:
            console.print("Cancelled.")
            return

        clear_routine()
        console.print("[green]✓[/green] Routine cleared")

    else:
        console.print(f"[red]Error:[/red] Unknown action: {action}")
        console.print("Valid actions: run, add, remove, list, clear")
        raise typer.Exit(1)


@app.command()
def loop(
    action: str = typer.Argument(
        "status",
        help="Action: enable, disable, status",
    ),
) -> None:
    """Configure the return loop behavior.

    When enabled, the dashboard re-launches after you detach from a session.

    Examples:
        kata loop           # Show current status
        kata loop enable    # Enable return loop
        kata loop disable   # Disable return loop
    """
    from kata.services.loop import is_loop_enabled, set_loop_enabled

    if action == "status":
        enabled = is_loop_enabled()
        status = "[green]enabled[/green]" if enabled else "[dim]disabled[/dim]"
        console.print(f"Return loop is {status}")

        if enabled:
            console.print("\nThe dashboard will re-launch after you detach from a session.")
        else:
            console.print("\nEnable with [bold]kata loop enable[/bold] to auto-relaunch after detach.")

    elif action == "enable":
        set_loop_enabled(True)
        console.print("[green]✓[/green] Return loop enabled")
        console.print("The dashboard will now re-launch after you detach from a session.")

    elif action == "disable":
        set_loop_enabled(False)
        console.print("[green]✓[/green] Return loop disabled")

    else:
        console.print(f"[red]Error:[/red] Unknown action: {action}")
        console.print("Valid actions: enable, disable, status")
        raise typer.Exit(1)


@app.command()
def switch(
    preview: bool = typer.Option(
        True,
        "--preview/--no-preview",
        "-p/-P",
        help="Show project preview pane in fzf",
    ),
) -> None:
    """Interactively switch to a project using fzf.

    Displays all registered projects with status indicators and allows fuzzy
    searching. Select a project to launch or attach to its tmux session.

    Requires fzf to be installed.

    Tmux keybinding example (add to ~/.tmux.conf):
        bind p display-popup -E -w 60% -h 60% "kata switch"
    """
    from kata.utils.fzf import is_fzf_available, run_fzf_picker

    if not is_fzf_available():
        console.print("[red]Error:[/red] fzf is not installed.")
        console.print("\nInstall fzf:")
        console.print("  macOS: [bold]brew install fzf[/bold]")
        console.print("  Ubuntu: [bold]sudo apt install fzf[/bold]")
        raise typer.Exit(1)

    registry = get_registry()
    projects = registry.list_all()

    if not projects:
        console.print("[dim]No projects registered.[/dim]")
        console.print("Use [bold]kata add[/bold] to add a project.")
        raise typer.Exit(0)

    # Get all session statuses in one call (fast)
    session_statuses = get_all_session_statuses()

    # Build fzf items with ANSI colors
    # Format: "● project-name (Group)" with colored status indicator
    items: list[str] = []
    name_map: dict[str, str] = {}  # Display string -> project name

    for project in sorted(projects, key=lambda p: (p.group, p.name)):
        status = session_statuses.get(project.name)

        # ANSI color codes for fzf
        if status and status.value == "active":
            indicator = "\033[32m●\033[0m"  # Green
        elif status and status.value == "detached":
            indicator = "\033[33m●\033[0m"  # Yellow
        else:
            indicator = "\033[90m○\033[0m"  # Dim/gray (idle or no session)

        display = f"{indicator} {project.name} ({project.group})"
        items.append(display)
        name_map[display] = project.name

    # Build preview command
    preview_cmd = "kata switch-preview {2}" if preview else None

    # Run fzf
    selected = run_fzf_picker(
        items=items,
        preview_cmd=preview_cmd,
        header="Select a project (Enter to switch, Esc to cancel)",
    )

    if not selected:
        # User cancelled
        raise typer.Exit(0)

    # Extract project name from selection
    # fzf may strip ANSI codes, so try direct lookup first, then parse
    project_name = name_map.get(selected)
    if not project_name:
        # Try to extract name from selection: "● name (group)" or "○ name (group)"
        import re
        match = re.search(r"[●○]\s+(\S+)\s+\(", selected)
        if match:
            project_name = match.group(1)

    if not project_name:
        console.print(f"[red]Error:[/red] Could not parse selection: {selected}")
        raise typer.Exit(1)

    try:
        project = registry.get(project_name)
        # Record that we opened this project
        project.record_open()
        registry.update(project)

        launch_or_attach(project)
    except ProjectNotFoundError:
        console.print(f"[red]Error:[/red] Project not found: {project_name}")
        raise typer.Exit(1)
    except SessionError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("switch-preview", hidden=True)
def switch_preview(
    name: str = typer.Argument(..., help="Name of the project to preview"),
) -> None:
    """Show project details for fzf preview pane (internal use)."""
    from kata.utils.git import get_branch_name, is_git_repository

    registry = get_registry()

    try:
        project = registry.get(name)
    except ProjectNotFoundError:
        console.print(f"[red]Project not found:[/red] {name}")
        raise typer.Exit(1)

    # Get session status
    status = get_session_status(project.name)
    status_display = {
        "active": "[green]Active[/green]",
        "detached": "[yellow]Detached[/yellow]",
        "idle": "[dim]Idle[/dim]",
    }.get(status.value, "Unknown")

    # Get git branch if available
    branch = None
    if is_git_repository(project.path):
        branch = get_branch_name(project.path)

    # Format last opened
    last_opened = "Never"
    if project.last_opened:
        last_opened = project.last_opened.strftime("%Y-%m-%d %H:%M")

    # Output preview info
    console.print(f"[bold]{project.name}[/bold]")
    console.print()
    console.print(f"[cyan]Path:[/cyan]    {project.path}")
    console.print(f"[cyan]Group:[/cyan]   {project.group}")
    if branch:
        console.print(f"[cyan]Branch:[/cyan]  {branch}")
    console.print(f"[cyan]Status:[/cyan]  {status_display}")
    console.print(f"[cyan]Opened:[/cyan]  {project.times_opened} times")
    console.print(f"[cyan]Last:[/cyan]    {last_opened}")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Kata - Terminal-centric workspace orchestrator for tmux.

    Run without arguments to open the TUI dashboard.
    """
    if ctx.invoked_subcommand is None:
        # No subcommand: launch TUI
        from kata.services.loop import is_loop_enabled, run_with_loop
        from kata.tui.app import run_dashboard

        if is_loop_enabled():
            run_with_loop()
        else:
            run_dashboard()


if __name__ == "__main__":
    app()
