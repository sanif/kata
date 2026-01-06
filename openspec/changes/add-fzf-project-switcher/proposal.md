# Change: Add fzf Project Switcher

## Why
Users need a fast way to switch between projects while inside a tmux session without returning to the full TUI dashboard. Currently, switching requires detaching from tmux and using the dashboard, which breaks workflow.

## What Changes
- Add `kata switch` CLI command with fzf-based interactive project picker
- Add `kata switch-preview` hidden command for fzf preview pane
- Create fzf integration helper utilities
- Document tmux keybinding setup for `prefix + p` popup

## Impact
- Affected specs: project-switching (new capability)
- Affected code: `kata/cli/app.py`, `kata/utils/fzf.py` (new)
- Dependencies: fzf must be installed (graceful fallback with error message)
