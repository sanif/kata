# CLI Capability

Command-line interface commands for non-interactive Kata operations.

## ADDED Requirements

### Requirement: Dashboard Launch Command

The system SHALL launch the TUI dashboard when invoked without arguments.

#### Scenario: Open dashboard
- **WHEN** `kata` is executed without arguments
- **THEN** the interactive TUI dashboard opens

### Requirement: Add Project Command

The system SHALL provide a CLI command to register projects.

#### Scenario: Add current directory
- **WHEN** `kata add` is executed without path argument
- **THEN** current working directory is registered

#### Scenario: Add specific path
- **WHEN** `kata add /path/to/project` is executed
- **THEN** specified path is registered

#### Scenario: Add with group
- **WHEN** `kata add --group Work` is executed
- **THEN** project is registered in the "Work" group

#### Scenario: Add with custom name
- **WHEN** `kata add --name my-project` is executed
- **THEN** project is registered with custom name instead of directory name

### Requirement: List Projects Command

The system SHALL provide a CLI command to list all registered projects.

#### Scenario: List in plain text
- **WHEN** `kata list` is executed
- **THEN** projects are printed as plain text, one per line

#### Scenario: List with details
- **WHEN** `kata list --long` is executed
- **THEN** projects include path, group, status, and last opened

#### Scenario: List as JSON
- **WHEN** `kata list --json` is executed
- **THEN** projects are output as JSON array for scripting

### Requirement: Kill Session Command

The system SHALL provide a CLI command to terminate sessions.

#### Scenario: Kill by name
- **WHEN** `kata kill project-name` is executed
- **THEN** the session for that project is terminated

#### Scenario: Kill all sessions
- **WHEN** `kata kill --all` is executed
- **THEN** all Kata-managed sessions are terminated

#### Scenario: Confirmation prompt
- **WHEN** `kata kill --all` is executed without --force
- **THEN** user is prompted to confirm before terminating

### Requirement: Edit Configuration Command

The system SHALL provide a CLI command to edit project configurations.

#### Scenario: Open in editor
- **WHEN** `kata edit project-name` is executed
- **THEN** project's YAML config opens in $EDITOR

#### Scenario: Editor not set
- **WHEN** $EDITOR is not set
- **THEN** fallback to vim, then nano, then error

#### Scenario: Project not found
- **WHEN** editing a non-existent project
- **THEN** error message indicates project not found

### Requirement: Scan Directories Command

The system SHALL provide a CLI command to discover and import projects.

#### Scenario: Scan directory
- **WHEN** `kata scan /path/to/workspace` is executed
- **THEN** all git repositories under that path are discovered

#### Scenario: Scan current directory
- **WHEN** `kata scan` is executed without path
- **THEN** current directory is scanned recursively

#### Scenario: Auto-import mode
- **WHEN** `kata scan --yes` is executed
- **THEN** all discovered projects are imported without prompting

#### Scenario: Assign group on scan
- **WHEN** `kata scan --group Work` is executed
- **THEN** all imported projects are assigned to "Work" group
