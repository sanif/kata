# Change: Add Kata Workspace Orchestrator

## Why

Developers waste significant time daily setting up their development environments—manually opening terminals, navigating directories, starting services, and arranging windows. **Kata** eliminates this friction by treating development environments as repeatable patterns that execute with a single keystroke.

The name "Kata" (Japanese: 型) reflects the philosophy: your dev environment is a form you practice daily. You shouldn't configure it every morning; you should perform it.

## What Changes

This is a greenfield implementation delivering a terminal-centric workspace orchestrator in three phases:

### Phase 1: White Belt (MVP)
- CLI `kata add` command to register projects
- Simple TUI dashboard listing all projects
- Launch/Attach logic with suspend capability
- Static YAML generation from default template

### Phase 2: Brown Belt (Management)
- Project grouping with collapsible folders in UI
- Smart Attach handling nested tmux sessions
- Visual status indicators (Active/Idle/Detached)
- `kata scan` for bulk repository import

### Phase 3: Black Belt (Mastery)
- Layout Wizard for visual pane editing
- Git integration (branch/dirty status in dashboard)
- "Morning Routine" to launch groups in background

## Impact

- **New specs created:**
  - `core` - Core data models and project configuration
  - `registry` - Project storage and metadata management
  - `sessions` - tmux session lifecycle management
  - `cli` - Command-line interface commands
  - `tui` - Terminal user interface dashboard

- **Tech stack:**
  - Python 3.10+
  - Textual (TUI framework)
  - Typer (CLI framework)
  - tmuxp (session backend)
  - libtmux (tmux server interface)

- **Data storage:** `~/.config/kata/`
  - `registry.json` - Project database
  - `configs/*.yaml` - tmuxp configuration files
