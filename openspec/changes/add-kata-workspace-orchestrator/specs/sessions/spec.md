# Sessions Capability

tmux session lifecycle management including launch, attach, and termination.

## ADDED Requirements

### Requirement: Session Launch

The system SHALL launch tmux sessions from tmuxp YAML configurations.

#### Scenario: Cold boot session
- **WHEN** session does not exist AND user selects project
- **THEN** tmuxp builds session from YAML config AND attaches user to session

#### Scenario: Hot switch session
- **WHEN** session already exists AND user selects project
- **THEN** user is attached to existing session without rebuilding

### Requirement: Context-Aware Attachment

The system SHALL detect tmux context and use appropriate attachment method to prevent nesting.

#### Scenario: Attach from outside tmux
- **WHEN** Kata runs outside any tmux session
- **THEN** `tmux attach-session` is used

#### Scenario: Switch from inside tmux
- **WHEN** Kata runs inside a tmux session
- **THEN** `tmux switch-client` is used instead of attach

#### Scenario: Detect tmux context
- **WHEN** determining attachment method
- **THEN** presence of TMUX environment variable indicates inside-tmux context

### Requirement: Session Termination

The system SHALL terminate tmux sessions individually or in bulk.

#### Scenario: Kill single session
- **WHEN** `kata kill project-name` is executed
- **THEN** the tmux session for that project is terminated

#### Scenario: Kill all sessions
- **WHEN** `kata kill --all` is executed
- **THEN** all Kata-managed tmux sessions are terminated

#### Scenario: Kill non-existent session
- **WHEN** attempting to kill a session that is not running
- **THEN** error message indicates session is not active

### Requirement: Session Status Querying

The system SHALL query the tmux server for session status information.

#### Scenario: List running sessions
- **WHEN** querying session status
- **THEN** libtmux returns list of active session names

#### Scenario: Check specific session
- **WHEN** checking if a specific session exists
- **THEN** boolean result indicates session existence

#### Scenario: Count attached clients
- **WHEN** determining Active vs Detached status
- **THEN** session's attached client count is checked

### Requirement: Return Loop

The system SHALL support returning to the dashboard after session detachment (optional feature).

#### Scenario: Detach with return disabled
- **WHEN** user detaches from session AND return loop is disabled
- **THEN** user returns to their previous shell

#### Scenario: Detach with return enabled
- **WHEN** user detaches from session AND return loop is enabled
- **THEN** Kata TUI dashboard is automatically re-launched

#### Scenario: Configure return behavior
- **WHEN** setting return loop preference
- **THEN** configuration persists in user settings
