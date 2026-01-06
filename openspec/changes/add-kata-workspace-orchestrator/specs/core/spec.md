# Core Capability

Core data models, configuration, and shared utilities for Kata.

## ADDED Requirements

### Requirement: Project Model

The system SHALL represent projects with a standardized data model containing name, path, group, configuration reference, and usage statistics.

#### Scenario: Create project from path
- **WHEN** a directory path is provided
- **THEN** a Project model is created with name derived from the directory name, absolute path, default group "Uncategorized", and timestamps

#### Scenario: Project serialization
- **WHEN** a Project is serialized to JSON
- **THEN** it includes all fields: name, path, group, config, created_at, last_opened, times_opened

### Requirement: Configuration Paths

The system SHALL use `~/.config/kata/` as the base configuration directory with standardized subdirectories.

#### Scenario: Config directory structure
- **WHEN** Kata initializes
- **THEN** it creates `~/.config/kata/` with `configs/` subdirectory if they do not exist

#### Scenario: Registry file location
- **WHEN** accessing the project registry
- **THEN** it reads from `~/.config/kata/registry.json`

### Requirement: Session Status Detection

The system SHALL detect the status of tmux sessions as Idle, Active, or Detached.

#### Scenario: Session not running
- **WHEN** no tmux session exists for a project
- **THEN** status is IDLE

#### Scenario: Session running with client
- **WHEN** tmux session exists AND a client is attached
- **THEN** status is ACTIVE

#### Scenario: Session running without client
- **WHEN** tmux session exists AND no client is attached
- **THEN** status is DETACHED

### Requirement: Project Type Detection

The system SHALL detect project types by examining directory contents for language-specific markers.

#### Scenario: Python project detection
- **WHEN** directory contains `pyproject.toml`, `setup.py`, or `requirements.txt`
- **THEN** project type is detected as "python"

#### Scenario: Node.js project detection
- **WHEN** directory contains `package.json`
- **THEN** project type is detected as "node"

#### Scenario: Go project detection
- **WHEN** directory contains `go.mod`
- **THEN** project type is detected as "go"

#### Scenario: Unknown project type
- **WHEN** no known markers are found
- **THEN** project type is detected as "generic"

### Requirement: YAML Template Generation

The system SHALL generate tmuxp-compatible YAML configurations from templates based on project type.

#### Scenario: Generate default template
- **WHEN** a project is registered
- **THEN** a tmuxp YAML config is created in `~/.config/kata/configs/{project-name}.yaml`

#### Scenario: Python template content
- **WHEN** project type is "python"
- **THEN** template includes windows for editor, shell with virtualenv activation, and test runner

#### Scenario: Node template content
- **WHEN** project type is "node"
- **THEN** template includes windows for editor, dev server, and test runner

#### Scenario: Generic template content
- **WHEN** project type is "generic"
- **THEN** template includes a single window with editor pane
