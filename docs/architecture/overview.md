# Kata Architecture Overview

## What It Is

A terminal workspace orchestrator for tmux. It manages development projects as persistent tmux sessions — register a project once, launch/switch to it with a keystroke.

## Layer Diagram

```
┌─────────────────────────────────────────────────────┐
│                   Entry Points                       │
│  CLI (Typer)  │  TUI Dashboard (Textual)  │  Popups │
│  kata add/    │  kata (no args)           │  Ctrl+  │
│  list/launch  │  Interactive browser      │  Space  │
├───────────────┴───────────────────────────┴─────────┤
│                   Services Layer                     │
│  Registry  │  Sessions  │  Notifications  │  Loop   │
│  (CRUD)    │  (tmux)    │  (daemon+IPC)   │  (re-   │
│            │            │                 │  launch)│
├─────────────────────────────────────────────────────┤
│                   Core Layer                         │
│  Models (Project, SessionStatus)                     │
│  Config (paths, migration)                           │
│  Settings (validated dataclass + JSON persistence)   │
│  Constants (timeouts, limits)                        │
│  Templates (tmuxp YAML generation)                   │
├─────────────────────────────────────────────────────┤
│                   Utilities                          │
│  git │ zoxide │ detection │ scanner │ paths │ colors │
├─────────────────────────────────────────────────────┤
│                   External                           │
│  tmux/tmuxp │ SQLite │ Unix sockets │ macOS notifs  │
└─────────────────────────────────────────────────────┘
```

## Data Flow

### Project Lifecycle

```
Register:  kata add ~/myproject
              │
              ▼
         detection.py ──► detect type (Python/Node/Go/Generic)
              │
              ▼
         templates.py ──► generate .kata.yaml (tmuxp config)
              │
              ▼
         registry.py  ──► save to ~/.config/kata/registry.json
```

```
Launch:    kata launch myproject
              │
              ▼
         sessions.py  ──► tmuxp load .kata.yaml (creates tmux session)
              │
              ▼
         tmux_style.py ──► apply color accent to tmux border
              │
              ▼
         attach/switch ──► tmux switch-client (if inside tmux)
                           tmux attach-session (if outside)
```

### Storage Architecture

```
~/.config/kata/
├── registry.json      ◄── Single source of truth for project metadata
├── settings.json      ◄── User preferences (theme, notifications, etc.)
├── notifications.db   ◄── SQLite (WAL mode) for notification history
├── notifyd.sock       ◄── Unix socket (daemon IPC, 0o600 permissions)
└── notifyd.pid        ◄── Daemon process tracking

~/any-project/
└── .kata.yaml         ◄── Per-project tmuxp layout config
```

Registry is JSON (simple, human-editable). Notifications use SQLite because they need indexing, querying by status, and pruning by age/count.

## Three Entry Points

### 1. CLI (`kata/cli/app.py`)
Standard Typer commands. Stateless — reads registry, does the thing, exits. Used for scripting, one-off operations, shell aliases.

### 2. TUI Dashboard (`kata/tui/app.py`)
Textual-based interactive browser. Polls tmux session status on a timer. Has its own widget tree:

```
KataDashboard
├── KataBanner (header + notification badge)
├── ProjectTree (grouped list, git status, color accents)
├── PreviewPane (project details, layout buttons)
├── RecentsPanel (zoxide frecency, adhoc sessions)
└── StatusBar (keybinding hints)
```

The TUI can't use libtmux (stdout capture conflict with Textual), so it uses `subprocess.run(["tmux", ...])` for all tmux operations.

### 3. Popups (`switch_strip.py`, `notify_strip.py`)
Launched inside `tmux display-popup`. Raw terminal rendering with Rich — no Textual framework. Reads keypresses via `os.read(fd, N)` in raw mode. These are the Ctrl+Space switcher and Ctrl+N notification center.

## Notification System

The most architecturally complex subsystem:

```
External Tools                    Daemon                      UI
─────────────                    ──────                      ──
Claude Code ──┐                                         ┌── TUI badge
Gemini ───────┤  hooks/*.py     ┌──────────┐            │
Codex ────────┤──────────────►  │ daemon.py │◄──────────┤── Popup
Tmux ─────────┘  (Unix socket)  │          │  subscribe │
                                │ store.py │            └── macOS notif
                                │ (SQLite) │
                                └──────────┘
                                     │
                              dispatch pipeline:
                              analyzer → dedup → state → summary → macos/audio
```

**Hooks** parse tool-specific output (Claude Code task completion, etc.) into normalized `Notification` objects. The **daemon** runs as a separate process, receives notifications via Unix socket, stores in SQLite, broadcasts to subscribers. The **dispatch pipeline** decides whether to show macOS notifications, play sounds, or suppress (dedup, focus detection).

## Key Design Decisions

**Why distributed configs (`.kata.yaml` in each project)?**
Projects are portable. Move a project directory and its tmux layout config moves with it. The registry just stores metadata (name, group, shortcut, color).

**Why subprocess over libtmux in TUI?**
libtmux captures stdout/stderr, which conflicts with Textual's own terminal rendering. Discovered the hard way — documented in CLAUDE.md.

**Why a daemon for notifications?**
Multiple tmux sessions can have Claude Code running simultaneously. A single daemon deduplicates, stores, and broadcasts. Without it, each session would need its own notification stack.

**Why singleton pattern for Registry/Settings/Store?**
These are read frequently (every status poll, every UI render). Lazy-loaded singletons avoid re-reading files on every call. The tradeoff is thread-safety (now documented, not yet locked).

**Why JSON for registry, SQLite for notifications?**
Registry is small (<100 projects typically), human-editable, rarely written. Notifications are high-volume, need querying by status/source/session, need pruning — that's a database job.
