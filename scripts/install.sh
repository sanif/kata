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

# Detect Linux package manager
detect_pkg_manager() {
    if command -v apt &> /dev/null; then
        echo "apt"
    elif command -v dnf &> /dev/null; then
        echo "dnf"
    elif command -v pacman &> /dev/null; then
        echo "pacman"
    elif command -v zypper &> /dev/null; then
        echo "zypper"
    else
        echo "unknown"
    fi
}

# Get the actual Python bin directory from PATH (handles pyenv/asdf correctly)
get_python_bin_dir() {
    local python_path
    python_path=$(which python3 2>/dev/null)
    if [[ -n "$python_path" ]]; then
        dirname "$python_path"
    fi
}

# Get working pip command - use the pip from PATH's Python
get_pip_cmd() {
    local bin_dir
    bin_dir=$(get_python_bin_dir)

    # If we found a Python bin dir, prefer its pip
    if [[ -n "$bin_dir" ]] && [[ -x "$bin_dir/pip3" ]]; then
        echo "$bin_dir/pip3"
        return 0
    fi

    # Try uv with --system (for global install)
    if command -v uv &> /dev/null; then
        echo "uv pip"
        return 0
    fi
    # Try pip3 (common on macOS/Linux)
    if command -v pip3 &> /dev/null; then
        echo "pip3"
        return 0
    fi
    # Try pip
    if command -v pip &> /dev/null; then
        echo "pip"
        return 0
    fi
    # Fallback to python3 -m pip
    if command -v python3 &> /dev/null; then
        echo "python3 -m pip"
        return 0
    fi
    return 1
}

# Install system packages on macOS
install_macos_deps() {
    local deps=("$@")

    # Check for Homebrew
    if ! command -v brew &> /dev/null; then
        warn "Homebrew is not installed"
        info "Installing Homebrew (required for system dependencies)..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Add brew to path for this session
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [[ -f "/usr/local/bin/brew" ]]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    fi

    # Install each dependency
    for dep in "${deps[@]}"; do
        info "Installing $dep..."
        brew install "$dep" 2>/dev/null || warn "Failed to install $dep via brew"
    done
}

# Install system packages on Linux
install_linux_deps() {
    local deps=("$@")
    local pkg_manager
    pkg_manager=$(detect_pkg_manager)

    # Map generic names to package names per distro
    declare -A apt_names=( ["python3"]="python3" ["tmux"]="tmux" ["fzf"]="fzf" ["zoxide"]="zoxide" )
    declare -A dnf_names=( ["python3"]="python3" ["tmux"]="tmux" ["fzf"]="fzf" ["zoxide"]="zoxide" )
    declare -A pacman_names=( ["python3"]="python" ["tmux"]="tmux" ["fzf"]="fzf" ["zoxide"]="zoxide" )
    declare -A zypper_names=( ["python3"]="python3" ["tmux"]="tmux" ["fzf"]="fzf" ["zoxide"]="zoxide" )

    case "$pkg_manager" in
        apt)
            info "Updating apt cache..."
            sudo apt update -qq
            for dep in "${deps[@]}"; do
                local pkg="${apt_names[$dep]:-$dep}"
                info "Installing $pkg..."
                sudo apt install -y "$pkg" 2>/dev/null || warn "Failed to install $pkg"
            done
            ;;
        dnf)
            for dep in "${deps[@]}"; do
                local pkg="${dnf_names[$dep]:-$dep}"
                info "Installing $pkg..."
                sudo dnf install -y "$pkg" 2>/dev/null || warn "Failed to install $pkg"
            done
            ;;
        pacman)
            for dep in "${deps[@]}"; do
                local pkg="${pacman_names[$dep]:-$dep}"
                info "Installing $pkg..."
                sudo pacman -S --noconfirm "$pkg" 2>/dev/null || warn "Failed to install $pkg"
            done
            ;;
        zypper)
            for dep in "${deps[@]}"; do
                local pkg="${zypper_names[$dep]:-$dep}"
                info "Installing $pkg..."
                sudo zypper install -y "$pkg" 2>/dev/null || warn "Failed to install $pkg"
            done
            ;;
        *)
            error "Unknown package manager. Please install manually: ${deps[*]}"
            return 1
            ;;
    esac
}

# Install tmuxp via pip
install_tmuxp() {
    local pip_cmd
    pip_cmd=$(get_pip_cmd) || {
        error "No pip available to install tmuxp"
        return 1
    }

    info "Installing tmuxp via $pip_cmd..."
    if [[ "$pip_cmd" == "uv pip" ]]; then
        uv pip install tmuxp --quiet 2>/dev/null || {
            warn "uv install failed, trying with --system flag..."
            uv pip install --system tmuxp --quiet
        }
    else
        $pip_cmd install tmuxp --quiet 2>/dev/null || {
            warn "pip install failed, trying with --user flag..."
            $pip_cmd install --user tmuxp --quiet
        }
    fi
}

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

# Collect missing system dependencies (not tmuxp)
MISSING_SYSTEM=()
NEED_TMUXP=false

check_command "python3" || MISSING_SYSTEM+=("python3")
check_command "tmux" || MISSING_SYSTEM+=("tmux")
check_command "fzf" || MISSING_SYSTEM+=("fzf")

# Optional
if ! check_command "zoxide"; then
    warn "zoxide is optional but recommended for recents feature"
fi

if ! check_command "tmuxp"; then
    NEED_TMUXP=true
fi

# Install missing system dependencies
if [ ${#MISSING_SYSTEM[@]} -gt 0 ]; then
    echo ""
    warn "Missing system dependencies: ${MISSING_SYSTEM[*]}"

    if [[ "$OS" == "macos" ]]; then
        info "Installing via Homebrew..."
        install_macos_deps "${MISSING_SYSTEM[@]}"
    elif [[ "$OS" == "linux" ]]; then
        info "Installing via package manager..."
        install_linux_deps "${MISSING_SYSTEM[@]}"
    else
        error "Unsupported OS. Please install manually: ${MISSING_SYSTEM[*]}"
        exit 1
    fi

    # Verify installation
    echo ""
    info "Verifying installations..."
    STILL_MISSING=()
    for dep in "${MISSING_SYSTEM[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            STILL_MISSING+=("$dep")
        else
            success "$dep installed successfully"
        fi
    done

    if [ ${#STILL_MISSING[@]} -gt 0 ]; then
        error "Failed to install: ${STILL_MISSING[*]}"
        error "Please install these manually and re-run the script"
        exit 1
    fi
fi

# Install tmuxp if needed
if [ "$NEED_TMUXP" = true ]; then
    echo ""
    install_tmuxp
    if command -v tmuxp &> /dev/null; then
        success "tmuxp installed successfully"
    else
        warn "tmuxp may not be in PATH yet. You may need to restart your shell."
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

    # Determine best install method: pipx > uv > pip
    INSTALL_METHOD=""
    if command -v pipx &> /dev/null; then
        INSTALL_METHOD="pipx"
    elif command -v uv &> /dev/null; then
        INSTALL_METHOD="uv"
    else
        pip_cmd=$(get_pip_cmd) || {
            error "No pip/pipx/uv found. Install one of: pipx, uv, pip"
            exit 1
        }
        INSTALL_METHOD="pip"
    fi

    # Check Python version (requires 3.10+)
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 10 ]]; then
        error "Python 3.10+ required. Found: Python $PYTHON_VERSION"
        info "Install Python 3.10+ and try again"
        exit 1
    fi

    info "Using Python $PYTHON_VERSION"
    info "Installing with $INSTALL_METHOD..."

    install_kata() {
        case "$INSTALL_METHOD" in
            pipx)
                # pipx creates isolated environment, specify python3 to use correct version
                # --verbose shows pip errors, --force reinstalls if exists
                pipx install . --force --python python3 --verbose
                ;;
            uv)
                # uv pip with --system for global install
                uv pip install --system .
                ;;
            pip)
                $pip_cmd install . || $pip_cmd install --user .
                ;;
        esac
    }

    # Try to install, upgrade pip if it fails
    if ! install_kata; then
        warn "Installation failed, trying to upgrade pip first..."
        python3 -m pip install --upgrade pip || true

        if ! install_kata; then
            error "Failed to install kata. Please check your Python/pip setup."
            exit 1
        fi
    fi

    success "Kata installed from source"

    # Get the bin directory where kata should be installed
    PYTHON_BIN_DIR=$(get_python_bin_dir)

    # Rehash pyenv/asdf if in use (updates shims)
    if command -v pyenv &> /dev/null; then
        pyenv rehash 2>/dev/null || true
    fi
    if command -v asdf &> /dev/null; then
        asdf reshim python 2>/dev/null || true
    fi

    # Ensure kata binary exists in the correct location
    if [[ -n "$PYTHON_BIN_DIR" ]] && [[ ! -f "$PYTHON_BIN_DIR/kata" ]]; then
        # Find where kata was actually installed
        KATA_INSTALLED=$(find "$HOME/.pyenv" /usr/local -name "kata" -path "*/bin/kata" -type f 2>/dev/null | head -1)
        if [[ -n "$KATA_INSTALLED" ]] && [[ -f "$KATA_INSTALLED" ]]; then
            cp "$KATA_INSTALLED" "$PYTHON_BIN_DIR/kata" 2>/dev/null && chmod +x "$PYTHON_BIN_DIR/kata" && \
                info "Copied kata binary to $PYTHON_BIN_DIR"
        fi
    fi

    # Create shim if using pyenv and shim doesn't exist
    if [[ "$PYTHON_BIN_DIR" == *"pyenv"*"shims"* ]]; then
        PYENV_ROOT=$(echo "$PYTHON_BIN_DIR" | sed 's|/shims.*||')
        SHIMS_DIR="${PYENV_ROOT}/shims"
        if [[ ! -f "$SHIMS_DIR/kata" ]]; then
            # Find kata binary - search multiple possible pyenv locations
            KATA_BIN=""
            # Search common pyenv locations (handles symlinked $HOME)
            for pyenv_loc in "${PYENV_ROOT}/versions" "$HOME/.pyenv/versions" "/Users/$USER/.pyenv/versions"; do
                if [[ -d "$pyenv_loc" ]]; then
                    KATA_BIN=$(find "$pyenv_loc" -name "kata" -path "*/bin/kata" -type f 2>/dev/null | head -1)
                    [[ -n "$KATA_BIN" ]] && break
                fi
            done
            if [[ -n "$KATA_BIN" ]]; then
                cat > "$SHIMS_DIR/kata" << SHIMEOF
#!/usr/bin/env bash
set -e
exec "$KATA_BIN" "\$@"
SHIMEOF
                chmod +x "$SHIMS_DIR/kata"
                info "Created kata shim at $SHIMS_DIR/kata"
            fi
        fi
    fi
else
    error "Could not find kata source. Run this script from the kata directory."
    exit 1
fi

# Ensure ~/.local/bin is in PATH
ensure_path() {
    local bin_dir="$HOME/.local/bin"

    # Add to current session immediately
    if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
        export PATH="$bin_dir:$PATH"
    fi

    # Check if PATH is already configured in any common profile
    local all_profiles=(
        "$HOME/.zshrc"
        "$HOME/.bashrc"
        "$HOME/.bash_profile"
        "$HOME/.profile"
        "$HOME/.zprofile"
        "$HOME/.config/fish/config.fish"
    )

    for profile in "${all_profiles[@]}"; do
        if [[ -f "$profile" ]] && grep -q '\.local/bin' "$profile"; then
            success "PATH already configured in $profile"
            return 0
        fi
    done

    # Detect which shell config to use
    local shell_config=""
    local is_fish=false

    if [[ "$SHELL" == *"fish"* ]]; then
        is_fish=true
        shell_config="$HOME/.config/fish/config.fish"
        # Create fish config dir if needed
        mkdir -p "$HOME/.config/fish"
    elif [[ -n "$ZSH_VERSION" ]] || [[ "$SHELL" == *"zsh"* ]]; then
        shell_config="$HOME/.zshrc"
    elif [[ -n "$BASH_VERSION" ]] || [[ "$SHELL" == *"bash"* ]]; then
        # Prefer existing profile, otherwise use .bashrc
        if [[ -f "$HOME/.bash_profile" ]]; then
            shell_config="$HOME/.bash_profile"
        elif [[ -f "$HOME/.profile" ]]; then
            shell_config="$HOME/.profile"
        else
            shell_config="$HOME/.bashrc"
        fi
    else
        # Fallback to .profile (POSIX standard)
        shell_config="$HOME/.profile"
    fi

    # Add PATH to shell config
    if [[ -n "$shell_config" ]]; then
        echo "" >> "$shell_config"
        echo "# Added by kata installer" >> "$shell_config"
        if [[ "$is_fish" == true ]]; then
            echo 'fish_add_path -g $HOME/.local/bin' >> "$shell_config"
        else
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$shell_config"
        fi
        success "Added ~/.local/bin to PATH in $shell_config"
    fi
}

# Verify installation and setup PATH
NEED_SHELL_RELOAD=false
KATA_BIN=""

# Find where kata was installed
if command -v kata &> /dev/null; then
    KATA_BIN=$(which kata)
    success "Kata is now available: $KATA_BIN"
elif [[ -f "$HOME/.pyenv/shims/kata" ]]; then
    KATA_BIN="$HOME/.pyenv/shims/kata"
    # Ensure pyenv init is in shell profile
    if command -v pyenv &> /dev/null; then
        SHELL_RC=""
        if [[ "$SHELL" == *"zsh"* ]]; then
            SHELL_RC="$HOME/.zshrc"
        elif [[ "$SHELL" == *"bash"* ]]; then
            SHELL_RC="$HOME/.bashrc"
            [[ -f "$HOME/.bash_profile" ]] && SHELL_RC="$HOME/.bash_profile"
        fi
        if [[ -n "$SHELL_RC" ]] && [[ -f "$SHELL_RC" ]]; then
            if ! grep -q 'pyenv init' "$SHELL_RC"; then
                echo "" >> "$SHELL_RC"
                echo '# pyenv init (added by kata installer)' >> "$SHELL_RC"
                echo 'eval "$(pyenv init -)"' >> "$SHELL_RC"
                success "Added pyenv init to $SHELL_RC"
                NEED_SHELL_RELOAD=true
            fi
        fi
    fi
    success "Kata installed at $KATA_BIN"
elif [[ -f "$HOME/.local/bin/kata" ]]; then
    KATA_BIN="$HOME/.local/bin/kata"
    ensure_path
    success "Kata installed at $KATA_BIN"
    NEED_SHELL_RELOAD=true
else
    warn "Kata binary not found - installation may have failed"
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
        # Auto-reload tmux config if tmux is running
        if [[ -n "$TMUX" ]]; then
            tmux source-file "$TMUX_CONF" 2>/dev/null && success "Tmux config reloaded"
        else
            success "Tmux configured! Will apply on next tmux session"
        fi
    else
        info "Skipped. You can add manually later."
    fi
fi

# Enable return loop (default: yes)
echo ""
read -p "Enable return loop (dashboard re-launches after detach)? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    kata loop enable 2>/dev/null || "$HOME/.pyenv/shims/kata" loop enable 2>/dev/null || true
    success "Return loop enabled"
fi

# Done
echo ""
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════${NC}"
echo ""

# Show reload instructions if needed
if [[ "$NEED_SHELL_RELOAD" == true ]]; then
    echo -e "${YELLOW}To use kata, reload your shell:${NC}"
    echo ""
    echo "  source ~/.zshrc    # or: exec \$SHELL"
    echo ""
fi

echo "Quick start:"
echo "  1. Add a project:     kata add ~/myproject"
echo "  2. Open dashboard:    kata"
echo "  3. Switch projects:   Ctrl+Space (in tmux)"
echo "  4. Detach session:    Ctrl+Q"
echo ""
echo "For more info: kata --help"
echo ""
