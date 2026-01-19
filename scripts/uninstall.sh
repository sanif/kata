#!/usr/bin/env bash
#
# Kata Uninstall Script
# Removes kata and cleans up configuration
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo -e "${RED}╔═══════════════════════════════════════╗${NC}"
echo -e "${RED}║     Kata Uninstall Script             ║${NC}"
echo -e "${RED}╚═══════════════════════════════════════╝${NC}"
echo ""

# Uninstall via pip
info "Removing kata package..."
pip3 uninstall kata -y 2>/dev/null && success "Removed kata package" || warn "kata package not found"

# Remove shims from all pyenv locations
info "Removing pyenv shims..."
SHIM_LOCATIONS=(
    "$HOME/.pyenv/shims/kata"
    "/Users/$USER/.pyenv/shims/kata"
    "/Volumes/External/Users/$USER/.pyenv/shims/kata"
)

for shim in "${SHIM_LOCATIONS[@]}"; do
    if [[ -f "$shim" ]]; then
        rm -f "$shim" && success "Removed $shim"
    fi
done

# Remove binaries from pyenv versions
info "Removing kata binaries..."
find "$HOME/.pyenv/versions" -name "kata" -path "*/bin/kata" -type f -delete 2>/dev/null || true
find "/Users/$USER/.pyenv/versions" -name "kata" -path "*/bin/kata" -type f -delete 2>/dev/null || true
find "/Volumes/External/Users/$USER/.pyenv/versions" -name "kata" -path "*/bin/kata" -type f -delete 2>/dev/null || true

# Remove from ~/.local/bin if exists
if [[ -f "$HOME/.local/bin/kata" ]]; then
    rm -f "$HOME/.local/bin/kata" && success "Removed ~/.local/bin/kata"
fi

# Rehash pyenv
if command -v pyenv &> /dev/null; then
    pyenv rehash 2>/dev/null || true
fi

# Ask about config removal
echo ""
read -p "Remove kata tmux keybinding from ~/.tmux.conf? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [[ -f "$HOME/.tmux.conf" ]]; then
        # Remove kata-related lines
        sed -i '' '/# Kata workspace orchestrator/d' "$HOME/.tmux.conf" 2>/dev/null || \
            sed -i '/# Kata workspace orchestrator/d' "$HOME/.tmux.conf"
        sed -i '' '/kata switch/d' "$HOME/.tmux.conf" 2>/dev/null || \
            sed -i '/kata switch/d' "$HOME/.tmux.conf"
        success "Removed tmux keybinding"
    fi
fi

# Ask about data removal
echo ""
read -p "Remove kata data (~/.config/kata and ~/.local/share/kata)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$HOME/.config/kata" 2>/dev/null && success "Removed ~/.config/kata" || true
    rm -rf "$HOME/.local/share/kata" 2>/dev/null && success "Removed ~/.local/share/kata" || true
fi

# Verify removal
echo ""
if command -v kata &> /dev/null; then
    warn "kata is still found at: $(which kata)"
    warn "You may need to restart your shell or remove it manually"
else
    success "kata has been completely removed"
fi

echo ""
echo -e "${GREEN}Uninstall complete.${NC}"
echo ""
