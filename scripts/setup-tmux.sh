#!/usr/bin/env bash
#
# Kata Tmux Configuration Script
# Sets up tmux keybindings for Kata
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }

TMUX_CONF="$HOME/.tmux.conf"
KATA_TMUX_MARKER="# Kata workspace orchestrator"

echo ""
echo -e "${GREEN}Kata Tmux Configuration${NC}"
echo ""

# Check if already configured
if [ -f "$TMUX_CONF" ] && grep -q "$KATA_TMUX_MARKER" "$TMUX_CONF"; then
    success "Tmux already configured for Kata"
    echo ""
    info "Current Kata configuration in ~/.tmux.conf:"
    grep -A5 "$KATA_TMUX_MARKER" "$TMUX_CONF" | head -10
    echo ""
    exit 0
fi

# Show what will be added
info "This will add the following to ~/.tmux.conf:"
echo ""
echo -e "${YELLOW}$KATA_TMUX_MARKER"
echo 'bind-key -n C-Space display-popup -E -w 80% -h 70% "kata switch"'
echo -e "${NC}"
echo ""

read -p "Continue? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Create backup
    if [ -f "$TMUX_CONF" ]; then
        cp "$TMUX_CONF" "$TMUX_CONF.backup"
        info "Backup created: $TMUX_CONF.backup"
    fi

    # Add configuration
    echo "" >> "$TMUX_CONF"
    echo "$KATA_TMUX_MARKER" >> "$TMUX_CONF"
    echo 'bind-key -n C-Space display-popup -E -w 80% -h 70% "kata switch"' >> "$TMUX_CONF"

    success "Configuration added to ~/.tmux.conf"
    echo ""
    info "Reload tmux config with:"
    echo "  tmux source ~/.tmux.conf"
    echo ""
    info "Or restart tmux"
else
    info "Cancelled"
fi
