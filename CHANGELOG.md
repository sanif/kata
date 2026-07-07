# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed
- sdist no longer includes development files (`.kata.yaml`, `.beads/`, `openspec/`, `docs/plans/`, `prd.md`, `AGENTS.md`, `CLAUDE.md`)
- Fixed project URLs in `pyproject.toml` and `docs/guide.md`

### Added
- Added LICENSE file (MIT)

## [0.4.0] - 2026-04-08

### Added
- Git worktree support: create/switch/delete worktrees from a Ctrl+W popup, with `kata worktree-strip` command
- Alt+Tab style cycling between worktrees
- Animated spinner and loading indicator during worktree creation
- Worktree service with CRUD operations and metadata persistence

### Fixed
- Fixed worktree path encoding and Claude session resume/fork behavior
- Fixed fork session ID lookup and branch name input in the create popup
- Fixed kata config, session launch, and context seeding for worktrees
- Resolved git root through worktrees for the Ctrl+W popup
- Refreshed tree when a project moves to a different group

### Changed
- Redesigned worktree popup UI with improved visual hierarchy and bordered panel layout
- Cleaned up audit issues ahead of release

## [0.3.0] - 2026-03-28

### Added
- Notification system: SQLite-backed store, asyncio Unix socket daemon, macOS notifications with 6 sound packs
- Claude Code and Gemini CLI hook handlers with transcript parsing and per-type sound/volume/suppression settings
- TUI notification center (badge, modal, session-grouped tree view) with startup pruning
- Per-project colors: `kata color` command, presets, hex validation, tmux pane border and status bar recoloring
- Ctrl+Space Alt+Tab-style project switcher with recents panel and zoxide integration
- Save Layout feature to capture live tmux session state
- Interactive `kata uninstall` command
- Centralized constants module for timeouts

### Fixed
- Sanitized tmux session names with special characters
- Registry atomic writes (temp+rename) to prevent data corruption
- Parameterized SQL query for notification store `LIMIT` to prevent injection
- Restricted daemon Unix socket to owner-only permissions (0o600)
- PID file cleanup on daemon start failure
- Per-subscriber timeout to prevent daemon broadcast blocking
- Various switcher/context-menu color-apply and quoting fixes

### Changed
- Refactored `_Project` to a dataclass; extracted shared notification, git, and switcher helpers
- Replaced if/elif dispatch chains with dict-based dispatch in the context menu
- Redesigned README as a short marketing page plus full guide; added architecture docs and screenshots
- Redesigned logo/banner with circuit-node aesthetic

## [0.2.2] - 2026-01-22

### Fixed
- Reload registry from disk on TUI refresh
- Resolved ruff linting and formatting errors

### Changed
- Added pre-commit hooks for linting and tests

## [0.2.1] - 2026-01-22

### Fixed
- Sanitized tmux session names with special characters

## [0.2.0] - 2026-01-19

### Changed
- Updated package description

## [0.1.0] - 2026-01-19

Initial release: terminal workspace orchestrator for tmux with an fzf-style project switcher.

### Added
- Registry-backed project tracking with tmuxp session launch
- TUI dashboard with project tree, live status, and recents panel
- zoxide integration and popup search modal
- Save Layout to capture live tmux session state
- Project shortcuts (1-9 keybindings)

[Unreleased]: https://github.com/sanif/kata/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/sanif/kata/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/sanif/kata/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/sanif/kata/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/sanif/kata/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/sanif/kata/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/sanif/kata/releases/tag/v0.1.0
