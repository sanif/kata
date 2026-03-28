#!/usr/bin/env bash
#
# Set up fake Kata projects for demo/video recording.
#
# Usage:
#   ./scripts/demo_setup.sh          # Create fake projects + tmux sessions
#   ./scripts/demo_setup.sh teardown  # Remove everything and restore real registry
#
# After setup, use Kata normally:
#   kata                    # Dashboard with fake projects
#   Ctrl+Space              # Switcher popup with fake sessions
#   Ctrl+N                  # Notification popup
#
# Colors, shortcuts, git status all work with the fake projects.
#

set -e

KATA_CONFIG="$HOME/.config/kata"
REGISTRY="$KATA_CONFIG/registry.json"
BACKUP="$KATA_CONFIG/registry.json.demo-backup"
DEMO_ROOT="/tmp/kata-demo-projects"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
DIM='\033[2m'
NC='\033[0m'

# ── Teardown ─────────────────────────────────────────────────────────────

teardown() {
    echo ""
    echo -e "${CYAN}Tearing down demo...${NC}"

    # Kill demo tmux sessions
    for session in api-gateway dashboard-ui ml-pipeline auth-service mobile-app dotfiles blog kata-oss; do
        tmux kill-session -t "$session" 2>/dev/null && echo -e "  ${DIM}Killed session: $session${NC}" || true
    done

    # Restore real registry
    if [[ -f "$BACKUP" ]]; then
        mv "$BACKUP" "$REGISTRY"
        echo -e "  ${GREEN}✓${NC} Restored real registry"
    fi

    # Remove temp project dirs
    if [[ -d "$DEMO_ROOT" ]]; then
        rm -rf "$DEMO_ROOT"
        echo -e "  ${GREEN}✓${NC} Removed temp directories"
    fi

    echo -e "${GREEN}Done! Your real projects are back.${NC}"
    echo ""
}

# ── Setup ────────────────────────────────────────────────────────────────

setup() {
    echo ""
    echo -e "${CYAN}Setting up demo projects...${NC}"
    echo ""

    # Backup real registry
    if [[ -f "$REGISTRY" ]] && [[ ! -f "$BACKUP" ]]; then
        cp "$REGISTRY" "$BACKUP"
        echo -e "  ${GREEN}✓${NC} Backed up real registry"
    fi

    # Create temp project directories with markers
    mkdir -p "$DEMO_ROOT"

    # Work projects
    mkdir -p "$DEMO_ROOT/work/api-gateway"
    cd "$DEMO_ROOT/work/api-gateway" && git init -q && echo "module api-gateway" > go.mod
    echo "# API Gateway" > README.md && git add -A && git commit -qm "init" 2>/dev/null

    mkdir -p "$DEMO_ROOT/work/dashboard-ui"
    cd "$DEMO_ROOT/work/dashboard-ui" && git init -q && echo '{"name":"dashboard-ui"}' > package.json
    echo "# Dashboard UI" > README.md && git add -A && git commit -qm "init"
    git checkout -qb feat/charts 2>/dev/null && echo "// charts" > charts.js && git add -A && git commit -qm "charts" 2>/dev/null

    mkdir -p "$DEMO_ROOT/work/ml-pipeline"
    cd "$DEMO_ROOT/work/ml-pipeline" && git init -q && echo '[project]\nname="ml-pipeline"' > pyproject.toml
    echo "# ML Pipeline" > README.md && git add -A && git commit -qm "init"
    git checkout -qb experiment/v2 2>/dev/null && echo "# v2" >> README.md && git add -A && git commit -qm "v2" 2>/dev/null

    mkdir -p "$DEMO_ROOT/work/auth-service"
    cd "$DEMO_ROOT/work/auth-service" && git init -q && echo "module auth-service" > go.mod
    echo "# Auth Service" > README.md && git add -A && git commit -qm "init" 2>/dev/null

    mkdir -p "$DEMO_ROOT/work/mobile-app"
    cd "$DEMO_ROOT/work/mobile-app" && git init -q && echo '{"name":"mobile-app"}' > package.json
    echo "# Mobile App" > README.md && git add -A && git commit -qm "init"
    git checkout -qb develop 2>/dev/null && echo "// dev" > app.js && git add -A && git commit -qm "dev" 2>/dev/null

    # Personal projects
    mkdir -p "$DEMO_ROOT/personal/dotfiles"
    cd "$DEMO_ROOT/personal/dotfiles" && git init -q
    echo "# Dotfiles" > README.md && git add -A && git commit -qm "init" 2>/dev/null

    mkdir -p "$DEMO_ROOT/personal/blog"
    cd "$DEMO_ROOT/personal/blog" && git init -q && echo '{"name":"blog"}' > package.json
    echo "# Blog" > README.md && git add -A && git commit -qm "init" 2>/dev/null

    # Open Source
    mkdir -p "$DEMO_ROOT/oss/kata-oss"
    cd "$DEMO_ROOT/oss/kata-oss" && git init -q && echo '[project]\nname="kata"' > pyproject.toml
    echo "# Kata" > README.md && git add -A && git commit -qm "init"
    git checkout -qb feature/notifications 2>/dev/null && echo "# notif" >> README.md && git add -A && git commit -qm "notif" 2>/dev/null

    echo -e "  ${GREEN}✓${NC} Created 8 project directories with git repos"

    # Write a clean registry with ONLY demo projects (no real ones)
    python3 -c "
import json
from datetime import datetime, timedelta

now = datetime.now()
projects = [
    {'name': 'api-gateway', 'path': '$DEMO_ROOT/work/api-gateway', 'group': 'Work',
     'config': 'api-gateway.yaml', 'created_at': '2025-06-15T10:00:00',
     'last_opened': (now - timedelta(minutes=12)).isoformat(), 'times_opened': 128,
     'shortcut': 1, 'color': 'cyan'},
    {'name': 'dashboard-ui', 'path': '$DEMO_ROOT/work/dashboard-ui', 'group': 'Work',
     'config': 'dashboard-ui.yaml', 'created_at': '2025-08-03T10:00:00',
     'last_opened': (now - timedelta(hours=2)).isoformat(), 'times_opened': 87,
     'shortcut': 2, 'color': 'purple'},
    {'name': 'ml-pipeline', 'path': '$DEMO_ROOT/work/ml-pipeline', 'group': 'Work',
     'config': 'ml-pipeline.yaml', 'created_at': '2025-09-20T10:00:00',
     'last_opened': (now - timedelta(hours=5)).isoformat(), 'times_opened': 45,
     'shortcut': 3, 'color': 'orange'},
    {'name': 'auth-service', 'path': '$DEMO_ROOT/work/auth-service', 'group': 'Work',
     'config': 'auth-service.yaml', 'created_at': '2025-11-01T10:00:00',
     'last_opened': (now - timedelta(days=1)).isoformat(), 'times_opened': 62,
     'shortcut': None, 'color': 'green'},
    {'name': 'mobile-app', 'path': '$DEMO_ROOT/work/mobile-app', 'group': 'Work',
     'config': 'mobile-app.yaml', 'created_at': '2026-01-10T10:00:00',
     'last_opened': (now - timedelta(days=2)).isoformat(), 'times_opened': 33,
     'shortcut': None, 'color': 'rose'},
    {'name': 'dotfiles', 'path': '$DEMO_ROOT/personal/dotfiles', 'group': 'Personal',
     'config': 'dotfiles.yaml', 'created_at': '2024-03-01T10:00:00',
     'last_opened': (now - timedelta(days=3)).isoformat(), 'times_opened': 210,
     'shortcut': 9, 'color': 'teal'},
    {'name': 'blog', 'path': '$DEMO_ROOT/personal/blog', 'group': 'Personal',
     'config': 'blog.yaml', 'created_at': '2025-05-20T10:00:00',
     'last_opened': (now - timedelta(days=7)).isoformat(), 'times_opened': 18,
     'shortcut': None, 'color': 'amber'},
    {'name': 'kata-oss', 'path': '$DEMO_ROOT/oss/kata-oss', 'group': 'Open Source',
     'config': 'kata-oss.yaml', 'created_at': '2025-02-01T10:00:00',
     'last_opened': (now - timedelta(minutes=30)).isoformat(), 'times_opened': 340,
     'shortcut': 4, 'color': 'blue'},
]
registry = {'version': '1.0', 'projects': projects}
with open('$REGISTRY', 'w') as f:
    json.dump(registry, f, indent=2)
"
    echo -e "  ${GREEN}✓${NC} Wrote clean demo registry (no personal projects)"

    # Create some tmux sessions (so switcher shows active/detached)
    tmux new-session -d -s api-gateway -c "$DEMO_ROOT/work/api-gateway" 2>/dev/null || true
    tmux new-session -d -s dashboard-ui -c "$DEMO_ROOT/work/dashboard-ui" 2>/dev/null || true
    tmux new-session -d -s ml-pipeline -c "$DEMO_ROOT/work/ml-pipeline" 2>/dev/null || true
    tmux new-session -d -s auth-service -c "$DEMO_ROOT/work/auth-service" 2>/dev/null || true
    tmux new-session -d -s kata-oss -c "$DEMO_ROOT/oss/kata-oss" 2>/dev/null || true
    tmux new-session -d -s dotfiles -c "$DEMO_ROOT/personal/dotfiles" 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Created 6 tmux sessions (for switcher popup)"

    echo ""
    echo -e "${GREEN}Demo ready!${NC}"
    echo ""
    echo "  Run these to demo:"
    echo -e "    ${CYAN}kata${NC}                    # Dashboard with fake projects"
    echo -e "    ${CYAN}Ctrl+Space${NC}              # Switcher popup (in tmux)"
    echo -e "    ${CYAN}Ctrl+N${NC}                  # Notification popup (in tmux)"
    echo ""
    echo "  When done:"
    echo -e "    ${CYAN}./scripts/demo_setup.sh teardown${NC}"
    echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────

if [[ "${1:-}" == "teardown" ]]; then
    teardown
else
    setup
fi
