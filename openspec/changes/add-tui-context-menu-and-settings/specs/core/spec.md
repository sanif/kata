# Core Capability

## ADDED Requirements

### Requirement: Global Settings Storage

The system SHALL store global settings in a JSON configuration file.

#### Scenario: Settings file location
- **WHEN** accessing global settings
- **THEN** settings are read from `~/.config/kata/settings.json`

#### Scenario: Initialize settings file
- **WHEN** settings file does not exist
- **THEN** default settings are used AND file is created on first write

#### Scenario: Parse error fallback
- **WHEN** settings file contains invalid JSON
- **THEN** default settings are used AND warning is logged

### Requirement: Settings Model

The system SHALL represent global settings with a standardized data model.

#### Scenario: Default settings
- **WHEN** no settings file exists
- **THEN** defaults are: loop_enabled=false, default_group="Uncategorized", refresh_interval=5, theme="default"

#### Scenario: Settings serialization
- **WHEN** settings are saved
- **THEN** JSON contains: loop_enabled, default_group, refresh_interval, theme

### Requirement: Loop Setting Access

The system SHALL provide programmatic access to loop mode setting.

#### Scenario: Read loop setting
- **WHEN** loop setting is queried
- **THEN** current boolean value is returned

#### Scenario: Write loop setting
- **WHEN** loop setting is changed
- **THEN** value persists to settings file immediately

#### Scenario: Migrate from legacy loop config
- **WHEN** settings.json doesn't exist AND loop_config.json exists
- **THEN** loop setting is migrated from loop_config.json

### Requirement: Default Group Setting

The system SHALL provide a configurable default group for new projects.

#### Scenario: Read default group
- **WHEN** default group is queried
- **THEN** current string value is returned

#### Scenario: Apply default group
- **WHEN** project is added without explicit group
- **THEN** default group from settings is used

### Requirement: Refresh Interval Setting

The system SHALL provide a configurable status refresh interval.

#### Scenario: Read refresh interval
- **WHEN** refresh interval is queried
- **THEN** current integer value (seconds) is returned

#### Scenario: Validate refresh interval
- **WHEN** refresh interval is set
- **THEN** value is clamped to range 1-60

### Requirement: Theme Setting

The system SHALL provide a configurable theme preference.

#### Scenario: Read theme
- **WHEN** theme is queried
- **THEN** current theme name string is returned

#### Scenario: Available themes
- **WHEN** listing available themes
- **THEN** returns: default, light, nord, dracula, solarized

#### Scenario: Invalid theme fallback
- **WHEN** stored theme name is not recognized
- **THEN** "default" theme is used
