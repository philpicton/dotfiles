#!/usr/bin/env bash

################################################################################
# Dotfiles Installation Script
# Description: Automated setup script for macOS dotfiles and dependencies
################################################################################

set -e

# Colors and formatting
BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Progress tracking
TOTAL_STEPS=0
CURRENT_STEP=0

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "\n${BOLD}${BLUE}===========================================================${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}===========================================================${NC}\n"
}

print_step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo -e "${BOLD}${GREEN}[${CURRENT_STEP}/${TOTAL_STEPS}]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

progress_bar() {
    local current=$1
    local total=$2
    local width=50
    local percentage=$((current * 100 / total))
    local filled=$((width * current / total))
    local empty=$((width - filled))

    printf "\r%sProgress:%s [" "$BOLD" "$NC"
    printf "%${filled}s" | tr ' ' '█'
    printf "%${empty}s" | tr ' ' '░'
    printf "] %s%%" "$percentage"

    if [ "$current" -eq "$total" ]; then
        echo ""
    fi
}

ask_yes_no() {
    local prompt="$1"
    local default="${2:-y}"
    local response

    if [[ "$default" == "y" ]]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi

    while true; do
        read -r -p "$(echo -e "${YELLOW}?${NC} $prompt")" response
        response=${response:-$default}
        case "$response" in
        [Yy]*) return 0 ;;
        [Nn]*) return 1 ;;
        *) echo "Please answer yes or no." ;;
        esac
    done
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

################################################################################
# Installation Functions
################################################################################

install_xcode_cli_tools() {
    print_step "Installing Xcode Command Line Tools"

    if xcode-select -p &>/dev/null; then
        print_success "Xcode Command Line Tools already installed"
        return 0
    fi

    print_info "This may take a few minutes..."

    # Create a temporary file for tracking installation
    touch /tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress

    # Find the latest Command Line Tools package
    local cmd_line_tools
    cmd_line_tools=$(softwareupdate -l 2>/dev/null |
        grep "\*.*Command Line Tools" |
        tail -n 1 |
        sed 's/^[^C]* //')

    if [[ -n "$cmd_line_tools" ]]; then
        softwareupdate -i "$cmd_line_tools" --verbose
    else
        # Fallback method
        xcode-select --install 2>/dev/null || true
        print_info "Please click 'Install' in the dialog box that appeared"
        read -r -p "Press Enter once installation is complete..."
    fi

    rm -f /tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress

    if xcode-select -p &>/dev/null; then
        print_success "Xcode Command Line Tools installed successfully"
    else
        print_error "Failed to install Xcode Command Line Tools"
        return 1
    fi
}

install_homebrew() {
    print_step "Installing Homebrew"

    if command_exists brew; then
        print_success "Homebrew already installed"
        return 0
    fi

    print_info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >>~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        echo 'eval "$(/usr/local/bin/brew shellenv)"' >>~/.zprofile
        eval "$(/usr/local/bin/brew shellenv)"
    fi

    if command_exists brew; then
        print_success "Homebrew installed successfully"
    else
        print_error "Failed to install Homebrew"
        exit 1
    fi
}

install_homebrew_packages() {
    print_step "Installing Homebrew packages"

    local brewfile="$HOME/.dotfiles/install/Brewfile"

    if [[ ! -f "$brewfile" ]]; then
        print_error "Brewfile not found at $brewfile"
        return 1
    fi

    # Create a temporary Brewfile with selected packages
    local temp_brewfile="/tmp/Brewfile.tmp"
    : >"$temp_brewfile"

    # Always install required formulae and casks
    print_info "Adding required packages..."
    sed -n '/# Formulae (Required)/,/# Casks (Required)/p' "$brewfile" | grep -E "^brew " >>"$temp_brewfile"
    sed -n '/# Casks (Required)/,/# Optional Formulae/p' "$brewfile" | grep -E "^cask " >>"$temp_brewfile"

    # Optional: SketchyBar
    if ask_yes_no "Install SketchyBar?"; then
        grep -E "^(tap \"felixkratz|brew \"sketchybar)" "$brewfile" >>"$temp_brewfile"
    fi

    # Optional: AeroSpace
    if ask_yes_no "Install AeroSpace (window manager)?"; then
        grep -E "^(tap \"nikitabobko|cask \"aerospace)" "$brewfile" >>"$temp_brewfile"
    fi

    # Optional: Ghostty
    if ask_yes_no "Install Ghostty (terminal emulator)?"; then
        grep -E "^cask \"ghostty\"" "$brewfile" >>"$temp_brewfile"
    fi

    # Optional: tmux
    if ask_yes_no "Install tmux (terminal multiplexer)?"; then
        grep -E "^brew \"tmux\"" "$brewfile" >>"$temp_brewfile"
    fi

    # Optional: Bun
    if ask_yes_no "Install Bun (JavaScript runtime)?"; then
        grep -E "^(tap \"oven-sh|brew \"bun)" "$brewfile" >>"$temp_brewfile"
    fi

    # Optional: GitHub Copilot CLI
    if ask_yes_no "Install GitHub Copilot CLI?"; then
        grep -E "^brew \"github-copilot-cli\"" "$brewfile" >>"$temp_brewfile"
    fi

    # Remove duplicates and sort
    sort -u "$temp_brewfile" -o "$temp_brewfile"

    print_info "Installing selected packages..."
    brew bundle --file="$temp_brewfile"

    rm "$temp_brewfile"
    print_success "Homebrew packages installed"
}

install_node_globals() {
    print_step "Installing Node.js global packages"

    if ! command_exists node; then
        print_warning "Node.js not installed, skipping global packages"
        return 0
    fi

    # Required packages
    local required_packages=(
        "neovim"
        "typescript"
        "typescript-language-server"
        "@vue/language-server"
    )

    # Optional npm packages
    local optional_packages=()
    # if ask_yes_no "Install GitHub Copilot CLI?"; then
    #     optional_packages+=("@githubnext/github-copilot-cli")
    # fi

    local all_packages=("${required_packages[@]}" "${optional_packages[@]}")
    local total=${#all_packages[@]}
    local current=0

    print_info "Installing npm packages..."
    for package in "${all_packages[@]}"; do
        current=$((current + 1))
        progress_bar "$current" "$total"
        npm install -g "$package" &>/dev/null || print_warning "Failed to install $package"
    done

    echo ""
    print_success "Node.js global packages installed"
}

clone_dotfiles() {
    print_step "Cloning dotfiles repository"

    local dotfiles_dir="$HOME/.dotfiles"

    if [[ -d "$dotfiles_dir" ]]; then
        print_success "Dotfiles already cloned"
        return 0
    fi

    local repo_url="$DOTFILES_REPO_URL"

    if [[ -z "$repo_url" ]]; then
        read -r -p "$(echo -e "${YELLOW}?${NC} Enter your dotfiles repository URL: ")" repo_url
    fi

    if [[ -z "$repo_url" ]]; then
        print_error "No repository URL provided"
        return 1
    fi

    git clone "$repo_url" "$dotfiles_dir"
    print_success "Dotfiles cloned to $dotfiles_dir"
}

setup_symlinks() {
    print_step "Setting up symlinks with GNU Stow"

    local dotfiles_dir="$HOME/.dotfiles"

    if [[ ! -d "$dotfiles_dir" ]]; then
        print_error "Dotfiles directory not found at $dotfiles_dir"
        return 1
    fi

    cd "$dotfiles_dir"

    # Get list of directories to stow (excluding non-config directories)
    local config_dirs
    mapfile -t config_dirs < <(find . -maxdepth 1 -type d ! -name '.' ! -name '.git' ! -name 'install' ! -name 'backgrounds' ! -name 'fonts' -exec basename {} \;)

    for dir in "${config_dirs[@]}"; do
        if ask_yes_no "Symlink $dir configuration?"; then
            stow -v "$dir" 2>&1 | grep -v "BUG in find_stowed_path" || true
            print_success "Symlinked $dir"
        fi
    done

    cd - >/dev/null
}

install_fonts() {
    print_step "Installing fonts"

    local fonts_dir="$HOME/.dotfiles/fonts"

    if [[ ! -d "$fonts_dir" ]]; then
        print_warning "Fonts directory not found, skipping font installation"
        return 0
    fi

    if ! ask_yes_no "Install fonts from fonts directory?"; then
        print_info "Skipping font installation"
        return 0
    fi

    local font_target_dir="$HOME/Library/Fonts"
    mkdir -p "$font_target_dir"

    local font_count=0
    shopt -s nullglob
    for font in "$fonts_dir"/*.{ttf,otf,TTF,OTF}; do
        if [[ -f "$font" ]]; then
            cp "$font" "$font_target_dir/"
            font_count=$((font_count + 1))
        fi
    done
    shopt -u nullglob

    if [[ $font_count -gt 0 ]]; then
        print_success "Installed $font_count fonts"
    else
        print_warning "No font files found"
    fi
}

configure_shell() {
    print_step "Configuring shell"

    # Set zsh as default shell if not already
    if [[ "$SHELL" != *"zsh"* ]]; then
        if ask_yes_no "Set zsh as default shell?"; then
            chsh -s "$(which zsh)"
            print_success "Default shell changed to zsh"
        fi
    else
        print_success "zsh already set as default shell"
    fi
}

################################################################################
# Main Installation Flow
################################################################################

main() {
    # Parse command-line arguments
    DOTFILES_REPO_URL="${1:-}"

    clear
    print_header "Dotfiles Installation Script"

    echo -e "${BOLD}This script will:${NC}"
    echo "  1. Install Xcode Command Line Tools"
    echo "  2. Install Homebrew"
    echo "  3. Clone your dotfiles repository"
    echo "  4. Install selected packages via Homebrew"
    echo "  5. Install Node.js global packages"
    echo "  6. Install fonts"
    echo "  7. Stow configuration files"
    echo "  8. Configure your shell"
    echo ""

    if ! ask_yes_no "Do you want to continue?" "y"; then
        print_info "Installation cancelled"
        exit 0
    fi

    # Calculate total steps
    TOTAL_STEPS=8

    print_header "Starting Installation"

    # Step 1: Xcode CLI Tools
    install_xcode_cli_tools

    # Step 2: Homebrew
    install_homebrew

    # Step 3: Clone dotfiles
    if [[ ! -d "$HOME/.dotfiles" ]]; then
        clone_dotfiles
    else
        CURRENT_STEP=$((CURRENT_STEP + 1))
        print_success "Dotfiles directory already exists"
    fi

    # Step 4: Homebrew packages
    install_homebrew_packages

    # Step 5: Node globals
    install_node_globals

    # Step 6: Fonts
    install_fonts

    # Step 7: Symlinks
    setup_symlinks

    # Step 8: Shell configuration
    configure_shell

    print_header "Installation Complete!"

    echo -e "${GREEN}${BOLD}✓ Your dotfiles have been installed successfully!${NC}\n"
    echo -e "${BOLD}Next steps:${NC}"
    echo "  1. Restart your terminal or run: source ~/.zshrc"
    echo "  2. Review your configurations in ~/.dotfiles"
    echo "  3. Customize as needed"
    echo ""
    echo -e "${BOLD}Installed to:${NC} $HOME/.dotfiles"
    echo ""

    if ask_yes_no "Would you like to restart your shell now?" "y"; then
        exec zsh -l
    fi
}

# Run main function
main "$@"
