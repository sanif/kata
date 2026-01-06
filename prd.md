
---

# **Product Requirements Document: Kata**

| **Project Name** | **Kata** |
| --- | --- |
| **Version** | 1.0 (Draft) |
| **Status** | In Planning |
| **Target Audience** | Polyglot Developers, CTOs, DevOps Engineers |
| **Tech Stack** | Python, Textual (TUI), Typer (CLI), Tmuxp (Backend) |

---

## **1. Executive Summary**

**Kata** is a terminal-centric workspace orchestrator. It treats development environments as repeatable patterns ("Katas") that can be executed perfectly with a single keystroke. It serves as a unified "Home Base" for the developer, replacing manual `tmux` session management with a disciplined, configuration-driven dashboard. It allows users to manage, categorize, and instantly launch complex multi-window project environments.

---

## **2. Philosophy & Identity**

The name **Kata** (Japanese: 型) refers to detailed choreographed patterns of movement practicing alone.

* **The Concept:** Your dev environment (Servers, DBs, Logs, Editor) is a "form" you practice daily.
* **The Goal:** Eliminate the friction of "setting up." You shouldn't *configure* your environment every morning; you should *perform* it.
* **Visual Language:** Minimalist, disciplined, high-contrast terminal UI.

---

## **3. Functional Requirements**

### **3.1 The "Home Base" (Dashboard)**

* **TUI Entry:** Running `kata` opens the interactive dashboard.
* **Project List:** Displays all registered projects, grouped by category (e.g., *Work, Personal, Infrastructure*).
* **Status Indicators:**
* 🟢 **Active:** Session is running and alive.
* ⚪ **Idle:** Session is not created.
* 🟡 **Detached:** Session is running but no client is attached.


* **Smart Search:** Fuzzy filtering across Project Name and Group.

### **3.2 Session Lifecycle (The "Practice")**

* **Launch/Attach:**
* *Scenario A (Cold Boot):* If the session is dead, Kata reads the YAML config, initializes the environment (splits windows, runs commands), and attaches.
* *Scenario B (Hot Switch):* If the session is running, Kata simply switches the view to it.


* **Context Awareness (The "No-Nesting" Rule):**
* Kata detects if it is running *inside* a tmux session.
* If **Inside:** It uses `tmux switch-client` to seamlessly swap projects.
* If **Outside:** It uses `tmux attach`.


* **The "Return" Loop:** When a user detaches from a session (`Ctrl+b, d`), Kata immediately catches the focus and re-renders the Dashboard, ready for the next selection.

### **3.3 Configuration & Management**

* **Schema:** Uses standard **`tmuxp` (YAML)** files.
* **Auto-Config:**
* Command: `kata add .`
* Action: Detects project type (Node, Python, Go) and generates a sensible default YAML layout automatically.


* **Groups:** Users can organize projects into collapsible folders.
* **Metadata:** A `registry.json` file tracks metadata that doesn't belong in the tmux config (like "Group Name" or "Times Opened").

---

## **4. CLI Command Interface**

Kata is hybrid. It works as a TUI but respects fast CLI inputs.

| Command | Arguments | Description |
| --- | --- | --- |
| `kata` | *None* | Opens the **Dojo** (TUI Dashboard). |
| `kata add` | `[path] --group [name]` | Adds current or specific path as a new Kata. |
| `kata list` | *None* | Prints a fast, plain-text list of projects. |
| `kata kill` | `[name] / --all` | Terminates a specific session or wipes all sessions. |
| `kata edit` | `[name]` | Opens the project's YAML config in `$EDITOR`. |
| `kata scan` | `[root_path]` | Recursively finds `.git` repos and offers to import them. |

---

## **5. User Interface (UX) Specification**

### **5.1 The Dashboard Layout**

The screen is divided into three panes:

1. **The Sidebar (Registry):** A tree view of Groups and Projects.
2. **The Stage (Preview):**
* **Header:** Project Name & Path.
* **Stats:** "Last Practiced: 2 hours ago", "Times Opened: 45".
* **Layout Preview:** A visual block diagram showing how the windows are split (e.g., "Editor [60%] | Logs [40%]").


3. **The Footer (Controls):**
* `[Enter] Begin` `[A] Add` `[E] Edit Config` `[D] Drop/Delete` `[Q] Quit`



### **5.2 The "Add" Wizard (TUI Form)**

Instead of editing text files, new users see a modal:

* **Step 1:** "Path to Project?" (File picker or text input).
* **Step 2:** "Group?" (Select existing or type new).
* **Step 3:** "Select Template" (Empty, Python/Django, Node/React, DevOps).

---

## **6. Technical Architecture**

### **6.1 Component Stack**

* **Core Logic:** `Python 3.10+`
* **TUI Library:** `Textual` (for async, CSS-grid layouts).
* **CLI Library:** `Typer` (for argument parsing).
* **Session Backend:** `tmuxp` (for parsing YAML and building sessions).
* **Tmux Interface:** `libtmux` (for low-level querying of the tmux server).

### **6.2 Data Storage**

**Location:** `~/.config/kata/`

1. **`registry.json`**: The "Database".
```json
{
  "projects": [
    {
      "name": "cureocity-backend",
      "group": "Work",
      "path": "~/dev/cureocity/be",
      "config": "cureocity-backend.yaml",
      "created_at": "2025-01-04T10:00:00"
    }
  ]
}

```


2. **`configs/*.yaml`**: The "Scrolls" (Configuration files).
```yaml
session_name: cureocity-backend
start_directory: ~/dev/cureocity/be
windows:
  - window_name: code
    layout: main-vertical
    panes:
      - vim .
      - git status

```



---

## **7. Roadmap & Phases**

### **Phase 1: The White Belt (MVP)**

* **Goal:** Basic functional launcher.
* **Features:**
* CLI `add` command.
* Simple List View TUI.
* Launch/Attach logic (with `suspend` capability).
* Static YAML generation (default template only).



### **Phase 2: The Brown Belt (Management)**

* **Goal:** Robust day-to-day management.
* **Features:**
* Grouping logic in UI.
* "Smart Attach" (handling nesting).
* Visual Status indicators (Green/Grey dots).
* `kata scan` for bulk import.



### **Phase 3: The Black Belt (Mastery)**

* **Goal:** Advanced features and polish.
* **Features:**
* Layout Wizard (Visual editor for panes).
* Git Integration (Show branch/dirty status in dashboard).
* "Morning Routine" (Launch specific group in background).



---
