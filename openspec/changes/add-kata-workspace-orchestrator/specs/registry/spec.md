# Registry Capability

Project storage, metadata management, and CRUD operations.

## ADDED Requirements

### Requirement: Project Registration

The system SHALL register projects by path, generating unique names and storing metadata in the registry.

#### Scenario: Register new project
- **WHEN** `kata add /path/to/project` is executed
- **THEN** project is added to registry with path, auto-generated name, default group, and created_at timestamp

#### Scenario: Register with custom group
- **WHEN** `kata add /path/to/project --group Work` is executed
- **THEN** project is registered with group set to "Work"

#### Scenario: Duplicate path prevention
- **WHEN** attempting to register an already-registered path
- **THEN** registration fails with error message indicating duplicate

#### Scenario: Non-existent path prevention
- **WHEN** attempting to register a path that does not exist
- **THEN** registration fails with error message indicating invalid path

### Requirement: Project Listing

The system SHALL list all registered projects with their metadata.

#### Scenario: List all projects
- **WHEN** `kata list` is executed
- **THEN** all projects are displayed with name, group, path, and status

#### Scenario: Empty registry
- **WHEN** no projects are registered
- **THEN** a message indicating no projects is displayed

### Requirement: Project Removal

The system SHALL remove projects from the registry and optionally delete associated configurations.

#### Scenario: Remove project
- **WHEN** project is deleted from registry
- **THEN** project entry is removed from registry.json

#### Scenario: Remove project with config cleanup
- **WHEN** project is deleted with cleanup option
- **THEN** both registry entry and YAML config file are removed

### Requirement: Group Management

The system SHALL organize projects into named groups for categorization.

#### Scenario: Move project to group
- **WHEN** project's group is updated
- **THEN** registry reflects new group assignment

#### Scenario: List projects by group
- **WHEN** filtering by group
- **THEN** only projects in that group are returned

#### Scenario: Create new group implicitly
- **WHEN** assigning a project to a non-existent group
- **THEN** the group is created automatically

### Requirement: Usage Statistics

The system SHALL track usage statistics for each project.

#### Scenario: Track session open
- **WHEN** a project session is launched
- **THEN** last_opened timestamp is updated AND times_opened counter is incremented

#### Scenario: Retrieve statistics
- **WHEN** querying project metadata
- **THEN** last_opened and times_opened are included in response

### Requirement: Bulk Import

The system SHALL scan directories recursively to discover and offer to import projects.

#### Scenario: Scan for git repositories
- **WHEN** `kata scan /path/to/workspace` is executed
- **THEN** all directories containing `.git` are discovered

#### Scenario: Filter already registered
- **WHEN** scanning discovers paths already in registry
- **THEN** those paths are excluded from import candidates

#### Scenario: Interactive import selection
- **WHEN** scan results are displayed
- **THEN** user can select which projects to import
