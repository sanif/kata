## Context

The Kata TUI dashboard uses Textual for its UI framework. We need to add two new interactive components:
1. A context menu that appears as a modal popup with action options
2. A settings screen for global configuration

### Stakeholders
- Users who want quick project actions without leaving TUI
- Users who prefer visual configuration over CLI commands

### Constraints
- Must integrate with existing Textual architecture
- Must not block the status refresh timer
- Settings must persist across sessions
- Context menu must be dismissible with Escape

## Goals / Non-Goals

### Goals
- Provide in-TUI access to common project actions (kill, delete, rename, move, open terminal)
- Provide in-TUI configuration for loop mode, default group, refresh interval, and theme
- Maintain consistency with existing TUI patterns and keybindings
- Persist settings to `~/.config/kata/settings.json`

### Non-Goals
- Custom theme editor (only predefined themes for now)
- Per-project settings (all settings are global)
- Context menu for groups (only projects)
- Undo/redo for actions

## Decisions

### Decision 1: Context Menu Implementation
**Choice**: Use Textual's `ModalScreen` for the context menu.

**Rationale**:
- Textual's modal screens handle focus management automatically
- Easy to dismiss with Escape
- Can render a vertical list of actions with keybindings

**Alternatives considered**:
- Custom popup widget - More work, less standard behavior
- Inline action bar - Takes up permanent screen space

### Decision 2: Settings Storage Format
**Choice**: JSON file at `~/.config/kata/settings.json`

**Rationale**:
- Consistent with existing `registry.json` and `loop_config.json`
- Easy to read/edit manually if needed
- Python's json module handles this natively

**Alternatives considered**:
- YAML - Requires additional dependency
- TOML - More complex for simple key-value settings

### Decision 3: Theme System
**Choice**: Predefined theme presets with named themes.

**Rationale**:
- Lower implementation complexity
- Easier to maintain visual consistency
- Users can still manually edit CSS if they want customization

**Themes to include**:
- `default` - Standard Textual dark theme
- `light` - Light mode variant
- `nord` - Nord color scheme
- `dracula` - Dracula color scheme
- `solarized` - Solarized dark

### Decision 4: Refresh Interval Setting
**Choice**: Integer setting with range 1-60 seconds, stored in settings.

**Rationale**:
- Allows balance between responsiveness and resource usage
- 5 seconds is a reasonable default
- 1 second minimum prevents excessive polling

## Risks / Trade-offs

### Risk: Settings file corruption
**Mitigation**: Validate JSON on load, fall back to defaults on parse errors.

### Risk: Theme changes not applying immediately
**Mitigation**: Require app restart for theme changes (document this in UI).

### Trade-off: Modal vs inline actions
- Modal blocks interaction with the main tree but is more familiar UX
- Inline actions would require more complex focus management
- **Decision**: Accept modal blocking as acceptable trade-off

## Migration Plan

1. Add new settings file, fall back to loop_config.json for loop setting if settings.json doesn't exist
2. Deprecate standalone loop_config.json in favor of settings.json
3. No breaking changes to existing CLI commands

## Open Questions

None - clarified with user that they want:
- Context menu (not direct key + confirm)
- All four settings types (loop, default group, refresh, theme)
- All four additional actions (delete, rename, move, open terminal)
