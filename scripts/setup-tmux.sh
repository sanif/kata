#!/usr/bin/env bash
#
# Kata Tmux Configuration Script
# Sets up tmux keybindings for Kata
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ${NC}  $1"; }
success() { echo -e "${GREEN}✓${NC}  $1"; }
warn() { echo -e "${YELLOW}⚠${NC}  $1"; }

TMUX_CONF="$HOME/.tmux.conf"
KATA_TMUX_MARKER="# Kata workspace orchestrator"

echo ""
echo -e "${BOLD}Kata Tmux Setup${NC}"
echo -e "${DIM}─────────────────────────────────${NC}"
echo ""

# Show what keybindings will be configured
echo -e "  ${BOLD}Ctrl+Space${NC}  Quick project switcher"
echo -e "  ${BOLD}Ctrl+N${NC}      Notification popup"
echo ""

# Check if already configured
if [ -f "$TMUX_CONF" ] && grep -q "$KATA_TMUX_MARKER" "$TMUX_CONF"; then
    success "Already configured in ~/.tmux.conf"
    echo ""

    # Check if config is outdated (still using old "kata switch" instead of "kata switch-strip")
    if grep -q 'kata switch"' "$TMUX_CONF" && ! grep -q 'kata switch-strip' "$TMUX_CONF"; then
        warn "Config is outdated — updating to new slim switcher..."
        # Remove old kata block
        sed -i.bak "/$KATA_TMUX_MARKER/,+2d" "$TMUX_CONF"
        # Re-add updated config
        echo "" >> "$TMUX_CONF"
        echo "$KATA_TMUX_MARKER" >> "$TMUX_CONF"
        echo 'bind-key -n C-Space display-popup -E -w 70 -h 3 "kata switch-strip"' >> "$TMUX_CONF"
        echo 'bind-key -n C-n display-popup -E -w 80% -h 60% "kata notify-popup"' >> "$TMUX_CONF"
        success "Updated to switch-strip"
    fi

    # Apply to current session if inside tmux
    if [[ -n "$TMUX" ]]; then
        tmux bind-key -n C-Space display-popup -E -w 70 -h 3 "kata switch-strip" 2>/dev/null
        tmux bind-key -n C-n display-popup -E -w 80% -h 60% "kata notify-popup" 2>/dev/null
        success "Bindings applied to current tmux session"
    fi
    echo ""
    exit 0
fi

# New installation
read -p "Add keybindings to ~/.tmux.conf? [Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    info "Skipped."
    echo ""

    # Still offer to apply for current session only
    if [[ -n "$TMUX" ]]; then
        read -p "Apply for this tmux session only (not saved)? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            tmux bind-key -n C-Space display-popup -E -w 70 -h 3 "kata switch-strip"
            tmux bind-key -n C-n display-popup -E -w 80% -h 60% "kata notify-popup"
            success "Bindings active for this session"
            echo ""
            echo -e "  ${DIM}Try it now: press Ctrl+Space${NC}"
            echo ""
        fi
    fi
    exit 0
fi

# Create backup
if [ -f "$TMUX_CONF" ]; then
    cp "$TMUX_CONF" "$TMUX_CONF.backup"
    info "Backup: ~/.tmux.conf.backup"
fi

# Add configuration
echo "" >> "$TMUX_CONF"
echo "$KATA_TMUX_MARKER" >> "$TMUX_CONF"
echo 'bind-key -n C-Space display-popup -E -w 70 -h 3 "kata switch-strip"' >> "$TMUX_CONF"
echo 'bind-key -n C-n display-popup -E -w 80% -h 60% "kata notify-popup"' >> "$TMUX_CONF"

success "Added to ~/.tmux.conf"

# Auto-apply to current session
if [[ -n "$TMUX" ]]; then
    tmux source-file "$TMUX_CONF" 2>/dev/null
    success "Applied to current tmux session"
    echo ""
    echo -e "  ${DIM}Try it now: press Ctrl+Space${NC}"
else
    echo ""
    echo -e "  ${DIM}Start tmux to use the keybindings${NC}"
fi
echo ""
