# Kata User Guide

Complete reference for installation, configuration, and usage.

---

## Installation

### Quick Install (Recommended)

**Prerequisites:** Python 3.10+, tmux, fzf, tmuxp

```bash
# macOS
brew install python@3.11 tmux fzf zoxide
pip install tmuxp

# Ubuntu/Debian
sudo apt install python3.10 tmux fzf
pip install tmuxp
```

```bash
# Install kata
pipx install kata-workspace --python python3.11
# Or: pip install kata-workspace
```

Then run `kata setup` to configure hooks and keybindings interactively.

### Install from Source

```bash
git clone https://github.com/kata-workspace/kata.git
cd kata
./scripts/install.sh
```

The install script checks prerequisites, installs Kata, configures tmux keybindings, and enables return loop.

### Manual Tmux Configuration

Add to `~/.tmux.conf`:

```bash
# Kata workspace orchestrator
bind-key -n C-Space run-shell -b "kata switch-strip"
bind-key -n C-S-Space run-shell -b "kata switch-strip --backward"
bind-key -n C-n run-shell -b "kata notify-popup"
bind-key -n C-q detach-client
```

Reload: `tmux source ~/.tmux.conf`

### Shell Configuration

Add to `~/.zshrc` or `~/.bashrc`:

```bash
export EDITOR=nvim   # or: vim, code, nano
```

---

## TUI Dashboard

Launch with `kata` (no arguments).

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Launch selected project |
| `1-9` | Quick launch by shortcut number |
| `a` | Add new project |
| `e` | Edit project config |
| `m` | Context menu |
| `s` | Settings |
| `/` | Search |
| `Tab` | Switch projects/recents focus |
| `k` | Quick kill session |
| `d` | Quick delete project |
| `n` | Notification center |
| `r` | Refresh status |
| `q` | Quit |

### Context Menu (`m`)

- Kill Session, Delete Project, Rename, Move to Group
- Open in Terminal, Save Layout, Set Shortcut (1-9)
- Toggle Notifications, Set Color

### Search (`/`)

Fuzzy-filter projects by name or group. `Escape` to clear.

---

## Tmux Session Keybindings

| Key | Action |
|-----|--------|
| `Ctrl+Space` | Project switcher popup |
| `Ctrl+Shift+Space` | Switcher (backward) |
| `Ctrl+N` | Notification center popup |
| `Ctrl+Q` | Detach (returns to dashboard if loop enabled) |

---

## AI Notification Hooks

Kata integrates with AI coding tools to notify you when tasks complete.

### Supported Tools

| Tool | Events | Hook Type |
|------|--------|-----------|
| **Claude Code** | Stop, SubagentStop, PreToolUse, Notification | JSON hooks in `~/.claude/settings.json` |
| **Gemini CLI** | AfterAgent, BeforeTool, SessionEnd, Notification | JSON hooks in `~/.gemini/settings.json` |
| **Codex CLI** | Agent turn complete | TOML notify in `~/.codex/config.toml` |

### Setup

```bash
kata setup    # Interactive — toggle which hooks to install
```

### Notification Features

- **macOS desktop notifications** via terminal-notifier
- **Sound alerts** with 6 sound packs (default, gentle, arcade, arabic, zen, funk)
- **Per-project enable/disable** in settings
- **Smart suppression** — deduplication, cooldowns after task completion
- **Notification center** — `Ctrl+N` popup grouped by project

---

## Layout Presets

When adding a project via TUI wizard, choose a layout:

| Preset | Windows |
|--------|---------|
| **Minimal** | editor |
| **Standard** | editor, shell, tests |
| **Full** | editor (split), shell, tests, build, logs |
| **Custom** | minimal — edit YAML with `kata edit` |

Python projects auto-activate virtualenv. Node projects include npm commands. Go projects include go test/build.

---

## Layout Saving

Capture your current tmux arrangement:

1. Arrange windows and panes as desired
2. Open context menu (`m` in TUI)
3. Select **Save Layout** (`l`)

Captures window names, pane layouts, running commands, and working directories.

---

## Morning Routine

Launch multiple projects at once:

```bash
kata routine add Work              # Add all "Work" projects
kata routine add important-app -p  # Add specific project
kata routine                       # Launch everything
```

---

## Configuration

### File Locations

```
~/.config/kata/
├── registry.json      # Project registry
├── settings.json      # App settings
├── routine.json       # Morning routine
├── notifications.db   # Notification history (SQLite)
└── tree_state.json    # TUI state

~/projects/my-app/
└── .kata.yaml         # Per-project tmuxp config
```

### Settings

Settings are managed via TUI (`s` key) or `~/.config/kata/settings.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| `loop_enabled` | false | Auto-relaunch dashboard after detach |
| `default_group` | Uncategorized | Default group for new projects |
| `refresh_interval` | 5 | Status poll interval (1-60 seconds) |
| `theme` | kata-dark | TUI theme |
| `notifications_enabled` | true | Master notification toggle |
| `notifications_sound_pack` | default | Sound pack (default, gentle, arcade, arabic, zen, funk) |
| `notifications_volume` | 1.0 | Sound volume (0.0-1.0) |
| `color_accent_enabled` | true | Color accent line in tmux |

---

## Themes

| Theme | Description |
|-------|-------------|
| `kata-dark` | Deep indigo with cyan/violet accents (default) |
| `kata-light` | Light background with warm accents |
| `kata-ocean` | Deep ocean blue palette |
| `kata-warm` | Cozy warm tones with amber highlights |
| `kata-glass` | Frosted glass — muted dark blue-gray |
| `kata-glass-light` | Light frosted glass — soft whites and silvers |
| `kata-rose` | Rose and pink tones |
| `kata-nord` | Nord color palette |
| `kata-mono` | Monochrome grayscale |
| `kata-ember` | Warm ember/fire tones |

---

## Project Colors

Assign colors to projects for visual identification:

1. Context menu (`m`) → Set Color
2. Choose from 12 presets or enter a hex code

Colors appear as an accent line in the tmux status bar and in the project tree.

**Presets:** blue, red, green, orange, purple, teal, rose, amber, cyan, lime, coral, slate

---

## Troubleshooting

### "fzf not found"
```bash
brew install fzf          # macOS
sudo apt install fzf      # Ubuntu
```

### "tmuxp not found"
```bash
pip install tmuxp
```

### "kata not in PATH"
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Notifications not showing (macOS)

1. Install: `brew install terminal-notifier`
2. System Settings → Notifications → terminal-notifier → Allow
3. Test: `terminal-notifier -title "Test" -message "Hello"`
4. Run: `kata setup`

---

## Uninstalling

```bash
kata uninstall
```

Interactive checklist to selectively remove hooks, keybindings, config data, and the package.
