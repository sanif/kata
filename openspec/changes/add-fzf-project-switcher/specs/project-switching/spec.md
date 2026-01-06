# Project Switching

## ADDED Requirements

### Requirement: Interactive Project Switcher
The system SHALL provide an interactive project switcher via `kata switch` that uses fzf for fuzzy selection.

#### Scenario: User switches projects with fzf
- **WHEN** user runs `kata switch` with fzf installed
- **THEN** fzf displays list of all registered projects with status indicators
- **AND** user can fuzzy search and select a project
- **AND** selected project is launched or attached via `launch_or_attach()`

#### Scenario: User switches from within tmux
- **WHEN** user runs `kata switch` from inside a tmux session
- **AND** selects a different project
- **THEN** tmux switches to the target session using `switch-client`
- **AND** no new terminal window is opened

#### Scenario: fzf not installed
- **WHEN** user runs `kata switch` without fzf installed
- **THEN** system displays error message with fzf installation instructions
- **AND** exits with non-zero status

### Requirement: Project Switcher Display Format
The system SHALL display projects in fzf with status indicators and group information.

#### Scenario: Project list format
- **WHEN** fzf displays the project list
- **THEN** each line shows: `[status] name (group)`
- **AND** status is `●` for active/detached sessions, `○` for idle
- **AND** active sessions are colored green, detached yellow, idle dim

### Requirement: Preview Pane Support
The system SHALL provide a hidden `kata switch-preview` command for fzf preview integration.

#### Scenario: Preview shows project details
- **WHEN** fzf calls `kata switch-preview <name>`
- **THEN** output includes: path, git branch (if available), session status, last opened time, open count

### Requirement: Tmux Keybinding Integration
The system SHALL support triggering via tmux keybinding using `display-popup`.

#### Scenario: Keybinding setup
- **WHEN** user adds `bind p display-popup -E -w 60% -h 60% "kata switch"` to tmux.conf
- **AND** presses `prefix + p` inside any tmux session
- **THEN** popup appears with project switcher
- **AND** selecting a project switches to that session
