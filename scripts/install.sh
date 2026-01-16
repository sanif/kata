#!/usr/bin/env bash
#
# Kata Installation Script
# Installs kata and configures tmux integration
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
echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Kata Installation Script          ║${NC}"
echo -e "${GREEN}║   Terminal Workspace Orchestrator     ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
echo ""

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
fi

# Check prerequisites
info "Checking prerequisites..."

check_command() {
    if command -v "$1" &> /dev/null; then
        success "$1 is installed"
        return 0
    else
        warn "$1 is not installed"
        return 1
    fi
}

MISSING=()

check_command "python3" || MISSING+=("python3")
check_command "tmux" || MISSING+=("tmux")
check_command "fzf" || MISSING+=("fzf")

# Optional
if ! check_command "zoxide"; then
    warn "zoxide is optional but recommended for recents feature"
fi

if ! check_command "tmuxp"; then
    MISSING+=("tmuxp")
fi

# Install missing dependencies
if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    warn "Missing dependencies: ${MISSING[*]}"

    if [[ "$OS" == "macos" ]]; then
        info "Install with: brew install ${MISSING[*]}"
        read -p "Install now with Homebrew? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            for dep in "${MISSING[@]}"; do
                if [[ "$dep" == "tmuxp" ]]; then
                    pip install tmuxp
                else
                    brew install "$dep"
                fi
            done
        else
            error "Please install missing dependencies and re-run this script"
            exit 1
        fi
    elif [[ "$OS" == "linux" ]]; then
        info "Install with your package manager:"
        info "  sudo apt install tmux fzf python3-pip"
        info "  pip install tmuxp"
        error "Please install missing dependencies and re-run this script"
        exit 1
    fi
fi

echo ""
info "Installing Kata..."

# Determine install method
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KATA_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$KATA_DIR/pyproject.toml" ]; then
    # Installing from source
    cd "$KATA_DIR"

    if command -v uv &> /dev/null; then
        info "Installing with uv..."
        uv pip install -e . --quiet
    else
        info "Installing with pip..."
        pip install -e . --quiet
    fi
    success "Kata installed from source"
else
    error "Could not find kata source. Run this script from the kata directory."
    exit 1
fi

# Verify installation
if command -v kata &> /dev/null; then
    success "Kata is now available: $(which kata)"
else
    warn "Kata installed but not in PATH"
    info "Add to your shell profile: export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
info "Configuring tmux integration..."

# Tmux configuration
TMUX_CONF="$HOME/.tmux.conf"
KATA_TMUX_MARKER="# Kata workspace orchestrator"

# Check if already configured
if [ -f "$TMUX_CONF" ] && grep -q "$KATA_TMUX_MARKER" "$TMUX_CONF"; then
    success "Tmux already configured for Kata"
else
    echo ""
    info "Add Ctrl+Space keybinding for project switching?"
    info "This will add the following to ~/.tmux.conf:"
    echo ""
    echo -e "${YELLOW}$KATA_TMUX_MARKER"
    echo 'bind-key -n C-Space display-popup -E -w 80% -h 70% "kata switch"'
    echo -e "${NC}"

    read -p "Add to ~/.tmux.conf? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "" >> "$TMUX_CONF"
        echo "$KATA_TMUX_MARKER" >> "$TMUX_CONF"
        echo 'bind-key -n C-Space display-popup -E -w 80% -h 70% "kata switch"' >> "$TMUX_CONF"
        success "Tmux configured! Reload with: tmux source ~/.tmux.conf"
    else
        info "Skipped. You can add manually later."
    fi
fi

# Enable return loop
echo ""
read -p "Enable return loop (dashboard re-launches after detach)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    kata loop enable 2>/dev/null || true
    success "Return loop enabled"
fi

# Done
echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""
echo "Quick start:"
echo "  1. Add a project:     kata add ~/myproject"
echo "  2. Open dashboard:    kata"
echo "  3. Switch projects:   Ctrl+Space (in tmux)"
echo "  4. Detach session:    Ctrl+Q"
echo ""
echo "For more info: kata --help"
echo ""
