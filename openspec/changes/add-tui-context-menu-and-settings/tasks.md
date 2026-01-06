## 1. Core Settings Infrastructure

- [ ] 1.1 Create `kata/core/settings.py` with Settings dataclass (loop_enabled, default_group, refresh_interval, theme)
- [ ] 1.2 Implement `load_settings()` function with JSON parsing and fallback to defaults
- [ ] 1.3 Implement `save_settings()` function with atomic write
- [ ] 1.4 Add migration logic to import from `loop_config.json` if `settings.json` doesn't exist
- [ ] 1.5 Add `AVAILABLE_THEMES` constant with theme names
- [ ] 1.6 Write unit tests for settings load/save/migrate

## 2. Context Menu Widget

- [ ] 2.1 Create `kata/tui/screens/context_menu.py` with ContextMenuScreen modal
- [ ] 2.2 Implement menu rendering with action labels and keybindings
- [ ] 2.3 Add keyboard navigation (up/down arrows, enter to select)
- [ ] 2.4 Add escape handling to close menu
- [ ] 2.5 Add direct key shortcuts (k, d, r, g, t) for actions
- [ ] 2.6 Emit action events back to dashboard

## 3. Context Menu Actions

- [ ] 3.1 Implement Kill Session action with confirmation dialog
- [ ] 3.2 Implement Delete Project action with confirmation dialog
- [ ] 3.3 Implement Rename Project action with input modal
- [ ] 3.4 Create group selector modal for Move to Group action
- [ ] 3.5 Implement Open in Terminal action with platform detection
- [ ] 3.6 Add macOS terminal detection (Terminal.app vs iTerm2)

## 4. Settings Screen

- [ ] 4.1 Create `kata/tui/screens/settings.py` with SettingsScreen modal
- [ ] 4.2 Add loop mode toggle widget
- [ ] 4.3 Add default group input widget
- [ ] 4.4 Add refresh interval input with validation (1-60)
- [ ] 4.5 Add theme selector dropdown/list
- [ ] 4.6 Implement auto-save on setting change
- [ ] 4.7 Add "restart required" notification for theme changes

## 5. Dashboard Integration

- [ ] 5.1 Add `m` keybinding to open context menu on selected project
- [ ] 5.2 Add `s` keybinding to open settings screen
- [ ] 5.3 Add `k` keybinding to open context menu with kill pre-selected
- [ ] 5.4 Update `d` keybinding to open context menu with delete pre-selected
- [ ] 5.5 Integrate refresh interval setting with existing timer
- [ ] 5.6 Update Footer to show new keybindings

## 6. Theme Implementation

- [ ] 6.1 Create theme CSS definitions for: default, light, nord, dracula, solarized
- [ ] 6.2 Add theme loading in app initialization
- [ ] 6.3 Store theme CSS in `kata/tui/themes/` directory

## 7. Testing & Validation

- [ ] 7.1 Write unit tests for context menu screen
- [ ] 7.2 Write unit tests for settings screen
- [ ] 7.3 Write integration tests for action flows (kill, delete, rename, move)
- [ ] 7.4 Manual testing of all keybindings
- [ ] 7.5 Verify settings persistence across app restarts
