# TUI Capability

Terminal User Interface dashboard and interactive components.

## ADDED Requirements

### Requirement: Dashboard Layout

The system SHALL display a three-pane dashboard layout with sidebar, preview, and footer.

#### Scenario: Sidebar displays project tree
- **WHEN** dashboard is open
- **THEN** left pane shows collapsible tree of groups and projects

#### Scenario: Preview displays project details
- **WHEN** a project is selected in sidebar
- **THEN** center pane shows project name, path, statistics, and layout preview

#### Scenario: Footer displays controls
- **WHEN** dashboard is open
- **THEN** bottom bar shows available keybindings

### Requirement: Project Tree Navigation

The system SHALL provide keyboard navigation for the project tree.

#### Scenario: Navigate with arrow keys
- **WHEN** up/down arrow keys are pressed
- **THEN** selection moves between projects

#### Scenario: Expand/collapse groups
- **WHEN** left/right arrow or enter is pressed on a group
- **THEN** group expands or collapses to show/hide projects

#### Scenario: Jump to project by typing
- **WHEN** user types characters
- **THEN** fuzzy search filters visible projects

### Requirement: Project Launch

The system SHALL launch selected projects from the dashboard.

#### Scenario: Launch with Enter
- **WHEN** Enter is pressed on a project
- **THEN** session is launched or attached

#### Scenario: Visual feedback during launch
- **WHEN** session is being built
- **THEN** loading indicator is displayed

### Requirement: Status Indicators

The system SHALL display visual status indicators for each project.

#### Scenario: Idle indicator
- **WHEN** project has no running session
- **THEN** grey/white circle is displayed

#### Scenario: Active indicator
- **WHEN** project has session with attached client
- **THEN** green circle is displayed

#### Scenario: Detached indicator
- **WHEN** project has session without attached client
- **THEN** yellow circle is displayed

### Requirement: Smart Search

The system SHALL provide fuzzy filtering across project names and groups.

#### Scenario: Open search
- **WHEN** `/` or search key is pressed
- **THEN** search input appears

#### Scenario: Filter results
- **WHEN** search query is entered
- **THEN** project list filters to matching entries

#### Scenario: Clear search
- **WHEN** Escape is pressed during search
- **THEN** search clears and full list is restored

### Requirement: Add Wizard

The system SHALL provide a guided wizard for adding new projects.

#### Scenario: Launch wizard
- **WHEN** `a` key is pressed on dashboard
- **THEN** add wizard modal opens

#### Scenario: Path selection step
- **WHEN** wizard step 1 is active
- **THEN** user can enter or browse for project path

#### Scenario: Group selection step
- **WHEN** wizard step 2 is active
- **THEN** user can select existing group or create new

#### Scenario: Template selection step
- **WHEN** wizard step 3 is active
- **THEN** user can choose from available templates

#### Scenario: Confirm and create
- **WHEN** wizard is completed
- **THEN** project is registered with selected options

### Requirement: Project Preview

The system SHALL display detailed information for the selected project.

#### Scenario: Show project metadata
- **WHEN** project is selected
- **THEN** name, path, and group are displayed

#### Scenario: Show usage statistics
- **WHEN** project is selected
- **THEN** last opened timestamp and times opened count are shown

#### Scenario: Show layout diagram
- **WHEN** project is selected
- **THEN** visual representation of window/pane layout is displayed

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
- **THEN** confirmation prompt appears for deletion

### Requirement: Git Integration (Phase 3)

The system SHALL display git status information in the dashboard.

#### Scenario: Show current branch
- **WHEN** project has git repository
- **THEN** current branch name is displayed

#### Scenario: Show dirty status
- **WHEN** project has uncommitted changes
- **THEN** dirty indicator is displayed next to project

### Requirement: Morning Routine (Phase 3)

The system SHALL support launching multiple sessions in background.

#### Scenario: Launch group in background
- **WHEN** morning routine is triggered for a group
- **THEN** all projects in group are launched as detached sessions

#### Scenario: Configure routine
- **WHEN** setting up morning routine
- **THEN** user can select which groups to include
