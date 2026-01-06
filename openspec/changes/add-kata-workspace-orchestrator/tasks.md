# Tasks: Kata Workspace Orchestrator

Implementation tasks organized by phase with dependencies noted.

## Phase 1: White Belt (MVP)

### 1. Project Setup
- [ ] 1.1 Initialize Python project with pyproject.toml (Python 3.10+)
- [ ] 1.2 Configure dependencies: textual, typer, tmuxp, libtmux
- [ ] 1.3 Set up project structure (kata/, cli/, tui/, core/, services/)
- [ ] 1.4 Configure development tools (ruff, mypy, pytest)

### 2. Core Data Models
- [ ] 2.1 Implement Project dataclass in `core/models.py`
- [ ] 2.2 Implement SessionStatus enum
- [ ] 2.3 Implement configuration paths in `core/config.py`
- [ ] 2.4 Add path validation utilities in `utils/paths.py`

### 3. Registry Service
- [ ] 3.1 Implement registry.json loading/saving in `services/registry.py`
- [ ] 3.2 Implement project CRUD operations (add, remove, update)
- [ ] 3.3 Implement duplicate path detection
- [ ] 3.4 Add unit tests for registry service

### 4. Project Type Detection
- [ ] 4.1 Implement project type detection in `utils/detection.py`
- [ ] 4.2 Add markers for Python, Node, Go, generic
- [ ] 4.3 Add unit tests for detection

### 5. Template Generation
- [ ] 5.1 Create YAML templates in `core/templates.py`
- [ ] 5.2 Implement template rendering for each project type
- [ ] 5.3 Implement template file writing to `~/.config/kata/configs/`
- [ ] 5.4 Add unit tests for template generation

### 6. Session Service (Basic)
- [ ] 6.1 Implement session existence check via libtmux in `services/sessions.py`
- [ ] 6.2 Implement session launch via tmuxp WorkspaceBuilder
- [ ] 6.3 Implement session attach (basic, outside tmux only)
- [ ] 6.4 Implement session status query (Idle/Active/Detached)
- [ ] 6.5 Add unit tests for session service

### 7. CLI: Add Command
- [ ] 7.1 Set up Typer app in `cli/app.py`
- [ ] 7.2 Implement `kata add [path] --group` command
- [ ] 7.3 Add path validation and error handling
- [ ] 7.4 Add CLI tests for add command

### 8. CLI: List Command
- [ ] 8.1 Implement `kata list` plain text output
- [ ] 8.2 Add status indicators in list output
- [ ] 8.3 Add CLI tests for list command

### 9. TUI: Basic Dashboard
- [ ] 9.1 Set up Textual app in `tui/app.py`
- [ ] 9.2 Implement basic project list widget
- [ ] 9.3 Implement project selection with Enter to launch
- [ ] 9.4 Wire CLI `kata` (no args) to launch TUI
- [ ] 9.5 Add integration tests for dashboard

### 10. Entry Point
- [ ] 10.1 Implement `__main__.py` entry point
- [ ] 10.2 Configure console_scripts in pyproject.toml
- [ ] 10.3 Manual end-to-end testing

## Phase 2: Brown Belt (Management)

### 11. Context-Aware Attachment
- [ ] 11.1 Implement TMUX environment detection
- [ ] 11.2 Implement switch-client for inside-tmux context
- [ ] 11.3 Update session service to use context-aware attach
- [ ] 11.4 Add tests for context switching

### 12. Group Management
- [ ] 12.1 Add group field handling in registry
- [ ] 12.2 Implement group listing in registry service
- [ ] 12.3 Implement move-to-group functionality
- [ ] 12.4 Add tests for group management

### 13. TUI: Visual Status Indicators
- [ ] 13.1 Implement status indicator widget (green/yellow/grey circles)
- [ ] 13.2 Add real-time status refresh in project list
- [ ] 13.3 Add CSS styling for indicators

### 14. TUI: Collapsible Groups
- [ ] 14.1 Implement tree view widget for groups/projects
- [ ] 14.2 Add expand/collapse with arrow keys
- [ ] 14.3 Remember expanded state between sessions
- [ ] 14.4 Add tests for tree navigation

### 15. TUI: Smart Search
- [ ] 15.1 Implement fuzzy search input widget
- [ ] 15.2 Wire search to filter project list
- [ ] 15.3 Add search keybinding (`/`)
- [ ] 15.4 Add tests for search functionality

### 16. CLI: Kill Command
- [ ] 16.1 Implement `kata kill [name]` command
- [ ] 16.2 Implement `kata kill --all` with confirmation
- [ ] 16.3 Add `--force` flag to skip confirmation
- [ ] 16.4 Add CLI tests for kill command

### 17. CLI: Scan Command
- [ ] 17.1 Implement recursive directory scanning
- [ ] 17.2 Detect `.git` directories as project markers
- [ ] 17.3 Filter already-registered paths
- [ ] 17.4 Implement interactive selection UI
- [ ] 17.5 Implement `--yes` auto-import mode
- [ ] 17.6 Add tests for scan command

### 18. Usage Statistics
- [ ] 18.1 Track last_opened on session launch
- [ ] 18.2 Increment times_opened counter
- [ ] 18.3 Display stats in TUI preview pane

## Phase 3: Black Belt (Mastery)

### 19. TUI: Project Preview Pane
- [x] 19.1 Implement preview pane layout
- [x] 19.2 Display project metadata (name, path, group)
- [x] 19.3 Display usage statistics
- [x] 19.4 Implement layout diagram widget

### 20. TUI: Layout Diagram
- [x] 20.1 Parse tmuxp YAML to extract window/pane structure
- [x] 20.2 Render ASCII block diagram of layout
- [x] 20.3 Show pane commands in diagram

### 21. CLI: Edit Command
- [x] 21.1 Implement `kata edit [name]` command
- [x] 21.2 Open YAML in $EDITOR with fallback chain
- [ ] 21.3 Add tests for edit command

### 22. TUI: Add Wizard
- [x] 22.1 Implement wizard modal screen
- [x] 22.2 Step 1: Path input/browser
- [x] 22.3 Step 2: Group selection
- [x] 22.4 Step 3: Template selection
- [x] 22.5 Wire wizard to registry add
- [ ] 22.6 Add tests for wizard flow

### 23. Git Integration
- [x] 23.1 Implement git branch detection
- [x] 23.2 Implement dirty status detection (uncommitted changes)
- [x] 23.3 Display branch in TUI project list
- [x] 23.4 Display dirty indicator in TUI

### 24. Morning Routine
- [x] 24.1 Implement background session launch
- [x] 24.2 Implement group batch launch
- [x] 24.3 Add morning routine configuration
- [x] 24.4 Add CLI/TUI trigger for routine

### 25. Return Loop (Optional)
- [x] 25.1 Implement detach detection wrapper
- [x] 25.2 Implement dashboard re-launch on detach
- [x] 25.3 Add configuration toggle for return loop

## Finalization

### 26. Documentation
- [ ] 26.1 Write README with installation and usage
- [ ] 26.2 Add example configurations
- [ ] 26.3 Document keyboard shortcuts

### 27. Release Preparation
- [ ] 27.1 Comprehensive manual testing on macOS
- [ ] 27.2 Test on Linux
- [ ] 27.3 Package for PyPI
