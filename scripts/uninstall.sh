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

# Uninstall via pipx or pip
info "Removing kata package..."
if command -v pipx &> /dev/null && pipx list 2>/dev/null | grep -q kata; then
    pipx uninstall kata 2>/dev/null && success "Removed kata (pipx)"
elif pip3 uninstall kata -y 2>/dev/null; then
    success "Removed kata package (pip)"
else
    warn "kata package not found in pipx or pip"
fi

# Detect pyenv root from PATH
get_pyenv_roots() {
    local roots=()
    # From PATH's python location
    local python_path
    python_path=$(which python3 2>/dev/null)
    if [[ "$python_path" == *"pyenv"* ]]; then
        local pyenv_root
        pyenv_root=$(echo "$python_path" | sed 's|/shims.*||')
        roots+=("$pyenv_root")
    fi
    # Standard locations (handles symlinked $HOME)
    [[ -d "$HOME/.pyenv" ]] && roots+=("$HOME/.pyenv")
    [[ -d "/Users/$USER/.pyenv" ]] && roots+=("/Users/$USER/.pyenv")
    # Return unique roots
    printf '%s\n' "${roots[@]}" | sort -u
}

# Remove shims from all pyenv locations
info "Removing pyenv shims..."
while IFS= read -r pyenv_root; do
    shim="$pyenv_root/shims/kata"
    if [[ -f "$shim" ]]; then
        rm -f "$shim" && success "Removed $shim"
    fi
done < <(get_pyenv_roots)

# Remove binaries from pyenv versions
info "Removing kata binaries..."
while IFS= read -r pyenv_root; do
    find "$pyenv_root/versions" -name "kata" -path "*/bin/kata" -type f -delete 2>/dev/null || true
done < <(get_pyenv_roots)

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
