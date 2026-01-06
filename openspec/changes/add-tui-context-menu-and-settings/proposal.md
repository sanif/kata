# Change: Add TUI Context Menu and Settings

## Why

The TUI dashboard currently provides basic project navigation and launch functionality, but lacks two key capabilities users expect:

1. **Context menu for project actions** - Users need to kill sessions, delete projects, rename projects, move projects between groups, and open projects in terminal without leaving the TUI. Currently, these actions require exiting to CLI.

2. **Global configuration in TUI** - The loop mode, default group, refresh interval, and theme settings are only configurable via CLI commands. Users should be able to view and modify these settings from within the TUI.

## What Changes

### TUI Context Menu
- Add `m` keybinding to open a context menu for the selected project
- Context menu options:
  - **Kill Session** (`k`) - Kill the project's tmux session (if running)
  - **Delete Project** (`d`) - Remove project from registry with confirmation
  - **Rename Project** (`r`) - Change project name via input field
  - **Move to Group** (`g`) - Select or create target group
  - **Open in Terminal** (`t`) - Open project path in new terminal window

### TUI Settings Screen
- Add `s` keybinding to open settings screen
- Settings available:
  - **Loop Mode** - Toggle return loop on/off
  - **Default Group** - Set default group for new projects
  - **Refresh Interval** - Control status update frequency (1-60 seconds)
  - **Theme** - Select from predefined themes or customize colors

### Core Configuration
- Extend the configuration system to store global settings
- Add settings file at `~/.config/kata/settings.json`

## Impact

- Affected specs: `tui`, `core`
- Affected code:
  - `kata/tui/app.py` - Add keybindings and screens
  - `kata/tui/screens/` - New context menu and settings screens
  - `kata/tui/widgets/` - Context menu widget
  - `kata/core/config.py` - Extended settings management
