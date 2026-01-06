# TUI Capability

## ADDED Requirements

### Requirement: Context Menu

The system SHALL provide a context menu for project actions accessible via keyboard shortcut.

#### Scenario: Open context menu
- **WHEN** `m` key is pressed with a project selected
- **THEN** a modal context menu appears with available actions

#### Scenario: Close context menu with Escape
- **WHEN** context menu is open AND `Escape` is pressed
- **THEN** context menu closes without performing any action

#### Scenario: Select action with key
- **WHEN** context menu is open AND action key is pressed (k/d/r/g/t)
- **THEN** corresponding action is executed

#### Scenario: Select action with Enter
- **WHEN** context menu is open AND arrow keys navigate to an action AND `Enter` is pressed
- **THEN** selected action is executed

### Requirement: Kill Session Action

The system SHALL allow killing a project's tmux session from the context menu.

#### Scenario: Kill running session
- **WHEN** `k` is pressed in context menu AND project has active session
- **THEN** session is killed AND status updates to Idle

#### Scenario: Kill with confirmation
- **WHEN** `k` is pressed in context menu
- **THEN** confirmation prompt appears before killing

#### Scenario: Kill non-running session
- **WHEN** `k` is pressed in context menu AND project has no running session
- **THEN** notification indicates no session to kill

### Requirement: Delete Project Action

The system SHALL allow deleting a project from the registry via context menu.

#### Scenario: Delete with confirmation
- **WHEN** `d` is pressed in context menu
- **THEN** confirmation prompt appears asking to confirm deletion

#### Scenario: Confirm deletion
- **WHEN** deletion is confirmed
- **THEN** project is removed from registry AND tree refreshes

#### Scenario: Cancel deletion
- **WHEN** deletion is cancelled
- **THEN** project remains in registry AND context menu closes

### Requirement: Rename Project Action

The system SHALL allow renaming a project via context menu.

#### Scenario: Open rename input
- **WHEN** `r` is pressed in context menu
- **THEN** input field appears pre-filled with current project name

#### Scenario: Submit new name
- **WHEN** new name is entered AND `Enter` is pressed
- **THEN** project name updates in registry AND tree refreshes

#### Scenario: Cancel rename
- **WHEN** `Escape` is pressed during rename
- **THEN** rename is cancelled AND original name preserved

#### Scenario: Duplicate name validation
- **WHEN** new name matches existing project name
- **THEN** error notification appears AND rename is not applied

### Requirement: Move to Group Action

The system SHALL allow moving a project to a different group via context menu.

#### Scenario: Open group selector
- **WHEN** `g` is pressed in context menu
- **THEN** group selection modal appears with existing groups listed

#### Scenario: Select existing group
- **WHEN** existing group is selected
- **THEN** project moves to selected group AND tree refreshes

#### Scenario: Create new group
- **WHEN** "New Group" option is selected
- **THEN** input field appears for new group name

#### Scenario: Submit new group
- **WHEN** new group name is entered AND `Enter` is pressed
- **THEN** group is created AND project moves to new group

### Requirement: Open in Terminal Action

The system SHALL allow opening a project's directory in a new terminal window.

#### Scenario: Open in default terminal
- **WHEN** `t` is pressed in context menu
- **THEN** new terminal window opens at project directory

#### Scenario: Platform-specific terminal
- **WHEN** opening terminal on macOS
- **THEN** Terminal.app or iTerm2 is used based on availability

#### Scenario: Terminal open error
- **WHEN** terminal cannot be opened
- **THEN** error notification appears with reason

### Requirement: Settings Screen

The system SHALL provide a settings screen accessible via keyboard shortcut.

#### Scenario: Open settings
- **WHEN** `s` key is pressed on dashboard
- **THEN** settings screen modal appears

#### Scenario: Close settings
- **WHEN** `Escape` is pressed on settings screen
- **THEN** settings screen closes AND dashboard is restored

#### Scenario: Save settings on change
- **WHEN** any setting is modified
- **THEN** setting is immediately persisted to settings file

### Requirement: Loop Mode Setting

The system SHALL allow toggling loop mode from settings screen.

#### Scenario: Display current loop state
- **WHEN** settings screen opens
- **THEN** loop mode toggle shows current enabled/disabled state

#### Scenario: Toggle loop mode
- **WHEN** loop mode toggle is activated
- **THEN** loop mode state changes AND persists immediately

### Requirement: Default Group Setting

The system SHALL allow setting the default group from settings screen.

#### Scenario: Display current default group
- **WHEN** settings screen opens
- **THEN** default group field shows current value

#### Scenario: Change default group
- **WHEN** new default group is entered
- **THEN** setting persists AND will be used for new projects

### Requirement: Refresh Interval Setting

The system SHALL allow configuring the status refresh interval from settings screen.

#### Scenario: Display current interval
- **WHEN** settings screen opens
- **THEN** refresh interval shows current value in seconds

#### Scenario: Change interval
- **WHEN** new interval value is entered
- **THEN** status refresh timer updates to new interval

#### Scenario: Validate interval range
- **WHEN** interval outside 1-60 range is entered
- **THEN** value is clamped to valid range

### Requirement: Theme Setting

The system SHALL allow selecting a theme from settings screen.

#### Scenario: Display available themes
- **WHEN** settings screen opens
- **THEN** theme selector shows list of predefined themes

#### Scenario: Current theme highlighted
- **WHEN** settings screen opens
- **THEN** currently active theme is visually indicated

#### Scenario: Apply theme
- **WHEN** new theme is selected
- **THEN** theme name persists AND notification indicates restart required

## MODIFIED Requirements

### Requirement: Keyboard Shortcuts

The system SHALL respond to keyboard shortcuts for common actions.

#### Scenario: Quit application
- **WHEN** `q` is pressed
- **THEN** application exits

#### Scenario: Add project shortcut
- **WHEN** `a` is pressed
- **THEN** add wizard opens

#### Scenario: Edit config shortcut
- **WHEN** `e` is pressed on selected project
- **THEN** config opens in external editor

#### Scenario: Delete project shortcut
- **WHEN** `d` is pressed on selected project
- **THEN** context menu opens with delete pre-selected

#### Scenario: Context menu shortcut
- **WHEN** `m` is pressed on selected project
- **THEN** context menu opens

#### Scenario: Settings shortcut
- **WHEN** `s` is pressed
- **THEN** settings screen opens

#### Scenario: Kill session shortcut
- **WHEN** `k` is pressed on selected project
- **THEN** context menu opens with kill pre-selected
