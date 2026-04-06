# Worktrees

Manage git worktrees for parallel development with isolated Claude Code sessions.

## Quick Start

1. Run `kata setup` and enable **Ctrl+W** under Tmux Bindings
2. Press `Ctrl+W` from any tmux session to open the worktree popup

## Popup Controls

| Key | Action |
|-----|--------|
| `↑`/`↓` or `j`/`k` | Navigate worktrees |
| `Enter` | Switch to selected worktree |
| `n` | Create new worktree |
| `d` | Delete worktree (safe — checks for unmerged changes) |
| `D` | Force delete worktree |
| `q` / `Esc` | Close popup |

## Creating Worktrees

Press `n` in the popup, enter a branch name, then choose a context mode:

| Mode | Key | What happens |
|------|-----|-------------|
| **Fork** | `f` | Forks your current Claude Code session into the new worktree. Full conversation history is carried over. Experimental — file path references from the parent may need updating. |
| **Summary** | `s` | Extracts a summary of your current Claude session and seeds it as system context in the new worktree. Lighter than fork. |
| **Clean** | `c` | Starts fresh. Claude loads only the project's CLAUDE.md. |

## How It Works

- Worktrees are stored in `.worktrees/` at the project root (auto-gitignored)
- Each worktree gets its own tmux session named `project:branch`
- Shared files (`.env`, `node_modules`, `.venv`, `.kata.yaml`) are symlinked from the parent
- Metadata is tracked in `.worktrees/.kata-worktrees.json`
- Session summaries are extracted from Claude Code's local JSONL files

## Session Summaries

The popup shows a 1-line summary of what Claude was last working on in each worktree. This is extracted from the most recent Claude Code session file for that directory.
