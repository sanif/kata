# Kata

**Terminal-centric workspace orchestrator for tmux**

Kata is a powerful CLI and TUI tool that transforms how you manage development workspaces. It combines the speed of tmux with intelligent project organization, giving you instant access to any project with a single keystroke.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)

---

## Why Kata?

**The Problem:** Developers juggle multiple projects daily. Each context switch involves:
- Navigating to the project directory
- Activating virtual environments
- Opening editors and terminals
- Remembering where you left off

**The Solution:** Kata eliminates this friction:
- **One keystroke** to switch between any project (`Ctrl+Space`)
- **Persistent sessions** that survive terminal closures
- **Smart templates** that auto-configure your workspace
- **Beautiful TUI** for visual project management

---

## Features at a Glance

| Feature | Description |
|---------|-------------|
| **Instant Switching** | Press `Ctrl+Space` anywhere to fuzzy-search and switch projects |
| **Session Persistence** | Tmux sessions survive terminal crashes and reboots |
| **Auto-Detection** | Automatically detects Python, Node.js, Go projects |
| **Smart Templates** | Pre-configured layouts with editor, shell, and test windows |
| **Morning Routine** | Launch multiple projects with one command |
| **Git Integration** | See branch, dirty state, and upstream status at a glance |
| **Return Loop** | Dashboard auto-relaunches after detaching from sessions |
| **Beautiful TUI** | Interactive dashboard with search, preview, and theming |

---

## Installation

### Prerequisites

- **Python 3.10+**
- **tmux** (terminal multiplexer)
- **tmuxp** (tmux session manager)
- **fzf** (fuzzy finder) - for project switching
- **jq** (JSON processor) - for fast project listing

```bash
# macOS
brew install tmux fzf jq
pip install tmuxp

# Ubuntu/Debian
sudo apt install tmux fzf jq
pip install tmuxp
```

### Install Kata

```bash
# Clone the repository
git clone https://github.com/kata-workspace/kata.git
cd kata

# Install with uv (recommended)
uv tool install -e .

# Or with pip
pip install -e .
```

### Post-Installation Setup

```bash
# Add to your shell profile (~/.zshrc or ~/.bashrc)
export EDITOR=nvim  # or your preferred editor

# Create the fast switcher script
mkdir -p ~/.local/bin
cat > ~/.local/bin/kata-switch << 'EOF'
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
export EDITOR=nvim
R=~/.config/kata/registry.json
[ -f "$R" ] || exit 0
P=$(jq -r '.projects[].name' "$R" 2>/dev/null | sort)
[ -z "$P" ] && exit 0
S=$(echo "$P" | fzf --height=60% --reverse --header="Select project")
[ -n "$S" ] && kata launch "$S"
EOF
chmod +x ~/.local/bin/kata-switch
```

---

## Quick Start

### 1. Add Your First Project

```bash
# Add current directory
kata add

# Add with a group
kata add ~/projects/my-app --group Work

# Scan and import multiple projects
kata scan ~/projects --depth 2
```

### 2. Launch the Dashboard

```bash
kata
```

This opens the interactive TUI where you can browse, search, and launch projects.

### 3. Launch a Project

```bash
# From CLI
kata launch my-app

# From TUI: select project and press Enter
```

### 4. Switch Between Projects

Once inside a tmux session, press `Ctrl+Space` to open the project switcher. Fuzzy-search your projects and hit Enter to switch instantly.

### 5. Return to Dashboard

Press `Ctrl+Q` to detach from the current session and return to the Kata dashboard.

---

## CLI Commands

### Project Management

#### `kata add [PATH] [--group GROUP]`
Register a new project with Kata.

```bash
kata add                          # Add current directory
kata add ~/projects/api           # Add specific path
kata add . --group "Work"         # Add with group
kata add . -g "Personal"          # Short form
```

**Features:**
- Auto-detects project type (Python/Node/Go/Generic)
- Generates tmuxp YAML configuration
- Handles name collisions with automatic suffixes
- Validates paths and checks for duplicates

#### `kata list [--group GROUP]`
Display all registered projects.

```bash
kata list                         # All projects
kata list --group Work            # Filter by group
kata list -g Personal             # Short form
```

**Output includes:**
- Session status (● Active, ● Detached, ● Idle)
- Project name, group, and path
- Color-coded table format

#### `kata remove NAME [--force]`
Remove a project from Kata.

```bash
kata remove old-project           # With confirmation
kata remove old-project --force   # Skip confirmation
kata remove old-project -f        # Short form
```

#### `kata move NAME GROUP`
Move a project to a different group.

```bash
kata move my-app "Archive"
```

#### `kata scan [PATH] [--depth N] [--group GROUP] [--yes]`
Recursively discover and import projects.

```bash
kata scan                         # Scan current directory
kata scan ~/code --depth 3        # Scan with depth
kata scan ~/work -g "Work" -y     # Auto-import all
```

**Detection markers:**
- `.git` directory
- `pyproject.toml`, `setup.py`, `requirements.txt` (Python)
- `package.json` (Node.js)
- `go.mod` (Go)

### Session Management

#### `kata launch NAME`
Launch or attach to a project's tmux session.

```bash
kata launch my-app
```

**Behavior:**
- Creates session from YAML config if not running
- Attaches to existing session if already running
- Records access statistics (times opened, last opened)

#### `kata kill [NAME] [--all] [--force]`
Terminate tmux sessions.

```bash
kata kill my-app                  # Kill specific session
kata kill --all                   # Kill all Kata sessions
kata kill -a -f                   # Kill all without confirmation
```

#### `kata switch`
Interactive project switcher using fzf.

```bash
kata switch
```

**Keybinding:** `Ctrl+Space` (auto-configured in Kata sessions)

### Configuration

#### `kata edit NAME`
Open a project's tmuxp config in your editor.

```bash
kata edit my-app
```

Uses `$EDITOR` or `$VISUAL`, falls back to nano/vim/vi.

#### `kata routine [ACTION] [TARGET] [--project]`
Manage the morning routine (batch session launch).

```bash
kata routine                      # Run the routine
kata routine add Work             # Add group to routine
kata routine add my-app -p        # Add specific project
kata routine remove Work          # Remove from routine
kata routine list                 # Show configuration
kata routine clear                # Clear all settings
```

#### `kata loop [ACTION]`
Configure return loop behavior.

```bash
kata loop                         # Show status
kata loop enable                  # Enable return loop
kata loop disable                 # Disable return loop
```

When enabled, the dashboard re-launches after you detach from any session.

---

## TUI Dashboard

Launch with `kata` (no arguments).

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ▸ kata | workspace orchestrator                            │
├─────────────────────────┬───────────────────────────────────┤
│                         │                                   │
│  ▼ Work                 │  my-app                           │
│    󰌠 my-app       ●     │                                   │
│    󰎙 frontend     ●     │  Path:   ~/projects/my-app        │
│                         │  Type:   Python 󰌠                 │
│  ▼ Personal             │  Status: Active                   │
│    󰉋 dotfiles     ●     │  Branch: main*                    │
│                         │                                   │
│                         │  ┌─────┬─────┬─────┐              │
│                         │  │edit │shell│tests│              │
│                         │  └─────┴─────┴─────┘              │
│                         │                                   │
│                         │  Opened: 42 times                 │
│                         │  Last:   2024-01-15 14:30         │
│                         │                                   │
├─────────────────────────┴───────────────────────────────────┤
│  [Enter] Launch  [a] Add  [e] Edit  [/] Search  [?] Help    │
└─────────────────────────────────────────────────────────────┘
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Launch selected project |
| `a` | Add new project |
| `e` | Edit project config |
| `m` | Open context menu |
| `s` | Open settings |
| `/` | Toggle search |
| `Escape` | Cancel/close |
| `?` | Show help |
| `k` | Quick kill session |
| `d` | Quick delete project |
| `r` | Refresh status |
| `q` | Quit dashboard |

### Search

Press `/` to activate search. Type to fuzzy-filter projects by name or group. Press `Escape` to clear and close search.

### Context Menu

Press `m` on any project to access:
- **Kill Session** - Terminate the tmux session
- **Delete Project** - Remove from registry
- **Rename Project** - Change the project name
- **Move to Group** - Change group assignment
- **Open Terminal** - Open directory in new terminal

### Settings

Press `s` to configure:
- **Return Loop** - Auto-relaunch dashboard after detach
- **Default Group** - Group for new projects
- **Refresh Interval** - Status update frequency (1-60 seconds)
- **Theme** - Visual theme (default, light, nord, dracula, solarized)

---

## Tmux Session Keybindings

When inside a Kata-managed tmux session:

| Key | Action |
|-----|--------|
| `Ctrl+Q` | Detach and return to dashboard |
| `Ctrl+Space` | Open project switcher (fzf popup) |

These keybindings are automatically configured when sessions are created.

---

## Layout Presets

When adding a project, Kata generates a tmuxp YAML configuration. Choose from these presets:

### Minimal
Single editor window.
```
┌──────────────┐
│    editor    │
└──────────────┘
```

### Standard (Default)
Editor, shell, and tests windows.
```
┌──────────────┬──────────────┬──────────────┐
│    editor    │    shell     │    tests     │
└──────────────┴──────────────┴──────────────┘
```
- Python: Auto-activates virtualenv
- Node: Ready for `npm run dev`
- Go: Ready for `go test`

### Full
Comprehensive setup with split panes.
```
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│    editor    │    shell     │    tests     │    build     │    logs      │
│   (split)    │              │              │              │   (split)    │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

### Custom
Starts minimal, edit the YAML yourself:
```bash
kata edit my-project
```

---

## Project Types

Kata auto-detects project types and configures templates accordingly:

| Type | Detection Markers | Template Features |
|------|-------------------|-------------------|
| **Python** | `pyproject.toml`, `setup.py`, `requirements.txt`, `Pipfile` | Virtualenv activation, pytest |
| **Node.js** | `package.json` | npm scripts ready |
| **Go** | `go.mod` | go test, go build |
| **Generic** | Any other | Basic editor setup |

---

## Git Integration

The TUI preview pane shows:
- **Current branch** - e.g., `main`, `feature/auth`
- **Dirty indicator** - `*` when uncommitted changes exist
- **Upstream status** - `↑2` ahead, `↓3` behind

Example: `main* ↑2 ↓1` means you're on main with uncommitted changes, 2 commits ahead, and 1 behind upstream.

---

## Morning Routine

Launch multiple projects at once for your daily workflow:

```bash
# Set up your routine
kata routine add Work              # Add all "Work" projects
kata routine add important-app -p  # Add specific project
kata routine list                  # Review configuration

# Every morning
kata routine                       # Launch everything
```

Output:
```
Starting morning routine (5 projects)...

  ✓ api-server
  ✓ frontend
  ⏭ database (already running)
  ✓ docs
  ✗ legacy-app: Config not found

Done! Launched: 3, Skipped: 1, Failed: 1
```

---

## Configuration Files

Kata stores configuration in `~/.config/kata/`:

```
~/.config/kata/
├── registry.json      # Project registry
├── settings.json      # App settings
├── routine.json       # Morning routine config
├── tree_state.json    # TUI tree expansion state
└── configs/           # tmuxp YAML configs
    ├── my-app.yaml
    ├── frontend.yaml
    └── ...
```

### registry.json
```json
{
  "version": "1.0",
  "projects": [
    {
      "name": "my-app",
      "path": "/home/user/projects/my-app",
      "group": "Work",
      "config": "my-app.yaml",
      "created_at": "2024-01-15T10:30:00",
      "last_opened": "2024-01-20T14:45:00",
      "times_opened": 42
    }
  ]
}
```

### settings.json
```json
{
  "loop_enabled": true,
  "default_group": "Uncategorized",
  "refresh_interval": 5,
  "theme": "default"
}
```

---

## Themes

Available themes for the TUI:

| Theme | Description |
|-------|-------------|
| `default` | Dark theme with balanced colors |
| `light` | Light background theme |
| `nord` | Arctic, bluish color palette |
| `dracula` | Dark theme with vibrant colors |
| `solarized` | Precision colors for readability |

Change theme in settings (`s` in TUI) or:
```bash
# Edit settings directly
$EDITOR ~/.config/kata/settings.json
```

---

## Tips & Best Practices

### Organize with Groups
```bash
kata add ~/work/api -g "Work"
kata add ~/work/frontend -g "Work"
kata add ~/personal/blog -g "Personal"
kata add ~/archived/old-app -g "Archive"
```

### Use the Morning Routine
```bash
kata routine add Work
kata routine add important-project -p
# Now just run `kata routine` each morning
```

### Enable Return Loop
```bash
kata loop enable
```
Now pressing `Ctrl+Q` takes you back to the dashboard instead of the bare terminal.

### Fast Project Switching
Inside any Kata session, press `Ctrl+Space` for instant fuzzy search across all projects.

### Customize Templates
```bash
kata edit my-project
```
Modify window names, add panes, change shell commands, etc.

### Scan Multiple Directories
```bash
kata scan ~/work -g "Work" -y
kata scan ~/personal -g "Personal" -y
```

---

## Troubleshooting

### "fzf not found"
```bash
# macOS
brew install fzf

# Ubuntu
sudo apt install fzf
```

### "tmuxp not found"
```bash
pip install tmuxp
# Or
uv tool install tmuxp
```

### "kata not in PATH"
```bash
# If installed with uv
uv tool install -e /path/to/kata

# Or add to PATH
export PATH="$HOME/.local/bin:$PATH"
```

### Session not switching in popup
The `kata-switch` script handles this. Ensure it's in your PATH:
```bash
which kata-switch  # Should show ~/.local/bin/kata-switch
```

### Projects not appearing
```bash
kata list  # Check if registered
kata scan ~/projects  # Re-scan if needed
```

---

## Architecture

```
kata/
├── cli/
│   └── app.py           # CLI commands (Typer)
├── tui/
│   ├── app.py           # Dashboard application (Textual)
│   ├── widgets/         # UI components
│   │   ├── tree.py      # Project tree widget
│   │   ├── preview.py   # Preview pane widget
│   │   └── search.py    # Search input widget
│   └── screens/         # Modal screens
│       ├── context_menu.py
│       ├── wizard.py    # Add project wizard
│       └── settings.py
├── services/
│   ├── registry.py      # Project storage
│   ├── sessions.py      # Tmux session management
│   ├── routine.py       # Morning routine
│   └── loop.py          # Return loop
├── utils/
│   ├── detection.py     # Project type detection
│   ├── scanner.py       # Directory scanning
│   ├── git.py           # Git integration
│   └── fzf.py           # FZF picker
└── core/
    ├── config.py        # Configuration paths
    ├── settings.py      # Settings management
    ├── models.py        # Data models
    └── templates.py     # tmuxp template generation
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `typer` | CLI framework |
| `textual` | TUI framework |
| `rich` | Terminal formatting |
| `libtmux` | Tmux Python API |
| `tmuxp` | Tmux session manager |
| `pyyaml` | YAML configuration |

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [tmux](https://github.com/tmux/tmux) - Terminal multiplexer
- [tmuxp](https://github.com/tmux-python/tmuxp) - Tmux session manager
- [Textual](https://github.com/Textualize/textual) - TUI framework
- [fzf](https://github.com/junegunn/fzf) - Fuzzy finder

---

**Happy coding with Kata!** 🥋
