# Design: Kata Workspace Orchestrator

## Context

Kata is a terminal-centric workspace orchestrator that manages development environments as repeatable patterns. It provides both a TUI dashboard and CLI commands for managing tmux-based project sessions.

**Key stakeholders:**
- Polyglot developers managing multiple projects
- DevOps engineers with complex multi-service environments
- CTOs evaluating developer productivity tools

**Constraints:**
- Must work seamlessly inside and outside tmux sessions
- Must not nest tmux sessions (use switch-client when inside tmux)
- Configuration files must be standard tmuxp YAML for portability
- Storage must be local-first (~/.config/kata/)

## Goals / Non-Goals

### Goals
- Eliminate daily environment setup friction
- Provide instant project switching with a single keystroke
- Support complex multi-window, multi-pane layouts
- Auto-detect project types for sensible defaults
- Visual dashboard showing all projects and their status

### Non-Goals
- Cloud sync or remote storage (local-first only)
- Non-tmux terminal multiplexers (screen, zellij)
- IDE integration (terminal-only)
- Collaborative session sharing

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
├─────────────────────┬───────────────────────────────────┤
│   CLI (Typer)       │         TUI (Textual)             │
│   kata add/list/    │   Dashboard, Project List,        │
│   kill/edit/scan    │   Add Wizard, Layout Preview      │
└─────────────────────┴───────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────┐
│                    Core Services                         │
├─────────────────────┬───────────────────────────────────┤
│  Registry Service   │      Session Service              │
│  - Project CRUD     │      - Launch/Attach              │
│  - Group management │      - Status detection           │
│  - Metadata         │      - Context awareness          │
└─────────────────────┴───────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────┐
│                    Backend Layer                         │
├─────────────────────┬───────────────────────────────────┤
│  tmuxp              │      libtmux                      │
│  - YAML parsing     │      - Server queries             │
│  - Session building │      - Session inspection         │
└─────────────────────┴───────────────────────────────────┘
```

## Decisions

### D1: Use tmuxp for session management

**Decision:** Use tmuxp's WorkspaceBuilder for creating sessions from YAML configs.

**Rationale:**
- tmuxp is mature, well-tested, actively maintained
- Standard YAML format enables portability
- Reduces implementation surface by ~500 lines
- Built-in support for complex layouts

**Alternatives considered:**
- Raw libtmux only: More control but 3x implementation effort
- Custom YAML parser: No benefit over tmuxp's proven parser

### D2: Textual for TUI framework

**Decision:** Use Textual for the dashboard and all interactive UI.

**Rationale:**
- Modern async-first design
- CSS-like styling for consistent visual language
- Rich widget library (trees, tables, forms)
- Active development by Textualize team

**Alternatives considered:**
- Rich + prompt_toolkit: Works but more assembly required
- Urwid: Older, callback-based, harder to style
- Curses: Too low-level for complex UIs

### D3: Typer for CLI

**Decision:** Use Typer for command-line argument parsing.

**Rationale:**
- Type hints for automatic validation
- Beautiful help output by default
- Seamless integration with Rich for formatted output
- Minimal boilerplate

**Alternatives considered:**
- Click: Typer is built on Click anyway
- argparse: More verbose, less beautiful output

### D4: JSON registry with YAML configs

**Decision:** Store metadata in `registry.json`, session configs in `configs/*.yaml`.

**Rationale:**
- JSON for machine-readable metadata (groups, stats, timestamps)
- YAML for human-editable session configs (windows, panes, commands)
- Separation allows editing configs in $EDITOR without corrupting metadata

**Alternatives considered:**
- Single JSON file: YAML configs harder to edit
- SQLite: Overkill for <1000 projects
- All YAML: Less suitable for metadata

### D5: Context-aware session switching

**Decision:** Detect if running inside tmux and use appropriate attach method.

**Implementation:**
```python
def attach_session(session_name: str):
    if os.environ.get("TMUX"):
        # Inside tmux: switch client
        subprocess.run(["tmux", "switch-client", "-t", session_name])
    else:
        # Outside tmux: attach
        subprocess.run(["tmux", "attach-session", "-t", session_name])
```

**Rationale:**
- Prevents nested tmux sessions (confusing UX)
- Seamless experience regardless of launch context
- Standard tmux behavior users expect

## Data Models

### Project

```python
@dataclass
class Project:
    name: str              # Unique identifier, derived from path
    path: str              # Absolute path to project root
    group: str             # Grouping category (Work, Personal, etc.)
    config: str            # Relative path to YAML config
    created_at: datetime   # When project was registered
    last_opened: datetime | None  # Last attach timestamp
    times_opened: int      # Usage counter
```

### Session Status

```python
class SessionStatus(Enum):
    IDLE = "idle"          # No tmux session exists
    ACTIVE = "active"      # Session running, client attached
    DETACHED = "detached"  # Session running, no client
```

### Registry Schema

```json
{
  "version": "1.0",
  "projects": [
    {
      "name": "project-name",
      "path": "/absolute/path",
      "group": "Work",
      "config": "project-name.yaml",
      "created_at": "2025-01-04T10:00:00Z",
      "last_opened": "2025-01-04T12:30:00Z",
      "times_opened": 45
    }
  ]
}
```

## File Structure

```
kata/
├── __init__.py
├── __main__.py          # Entry point
├── cli/
│   ├── __init__.py
│   ├── app.py           # Typer app
│   └── commands/
│       ├── __init__.py
│       ├── add.py
│       ├── list.py
│       ├── kill.py
│       ├── edit.py
│       └── scan.py
├── tui/
│   ├── __init__.py
│   ├── app.py           # Textual app
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── dashboard.py
│   │   └── add_wizard.py
│   └── widgets/
│       ├── __init__.py
│       ├── project_tree.py
│       ├── project_preview.py
│       └── layout_diagram.py
├── core/
│   ├── __init__.py
│   ├── models.py        # Data models
│   ├── config.py        # Configuration paths
│   └── templates.py     # Project type templates
├── services/
│   ├── __init__.py
│   ├── registry.py      # Project CRUD
│   └── sessions.py      # tmux lifecycle
└── utils/
    ├── __init__.py
    ├── detection.py     # Project type detection
    └── paths.py         # Path utilities
```

## Risks / Trade-offs

### R1: tmuxp API stability
- **Risk:** tmuxp API changes could break session loading
- **Mitigation:** Pin tmuxp version, test against specific version, abstract behind service layer

### R2: Textual learning curve
- **Risk:** Textual is relatively new, documentation gaps possible
- **Mitigation:** Start with simple widgets, iterate on UX

### R3: Cross-platform compatibility
- **Risk:** tmux not available on Windows
- **Mitigation:** Document as Unix/macOS/WSL only, detect and warn

### R4: Large registries
- **Risk:** 1000+ projects could slow JSON loading
- **Mitigation:** Lazy loading, consider SQLite migration path if needed

## Migration Plan

Not applicable - greenfield project.

## Phase Delivery

### Phase 1 Deliverables
- `kata` command opens TUI with project list
- `kata add [path]` registers new project
- `kata list` prints projects as plain text
- Basic session launch/attach
- Default YAML template generation

### Phase 2 Deliverables
- Group management (create, move projects)
- Visual status indicators in TUI
- Smart attach (tmux context detection)
- `kata scan` for bulk import
- `kata kill` for session management

### Phase 3 Deliverables
- Layout wizard (visual pane editor)
- Git status in dashboard
- Morning routine (background group launch)
- `kata edit` opens config in $EDITOR

## Open Questions

1. **Template library:** Should we ship templates for common stacks (Django, React, Go) or generate them dynamically from detection?
   - *Recommendation:* Ship basic templates, enhance detection over time

2. **Config location:** Should configs live in `~/.config/kata/configs/` or alongside projects as `.kata.yaml`?
   - *Recommendation:* Centralized in ~/.config/kata/ for simpler management

3. **Suspend behavior:** When user detaches, should Kata auto-reopen dashboard?
   - *Recommendation:* Optional via config, disabled by default to match standard tmux behavior
