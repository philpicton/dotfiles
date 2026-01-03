#!/usr/bin/env bash

################################################################################
# Dotfiles Installation Script
# Description: Automated setup script for macOS dotfiles and dependencies
################################################################################

set -euo pipefail

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

    # Avoid division by zero
    if [[ $total -eq 0 ]]; then
        return
    fi

    local percentage=$((current * 100 / total))
    local filled=$((width * current / total))
    local empty=$((width - filled))

    printf "\r\033[1mProgress:\033[0m ["
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
        read -r -p "$(echo -e "${YELLOW}?${NC} $prompt")" response </dev/tty
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
        read -r -p "Press Enter once installation is complete..." </dev/tty
    fi

    rm -f /tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress

    if xcode-select -p &>/dev/null; then
        print_success "Xcode Command Line Tools installed successfully"
    else
        print_error "Failed to install Xcode Command Line Tools"
        print_warning "Please install manually and run this script again"
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
        if ! grep -q '/opt/homebrew/bin/brew shellenv' ~/.zprofile 2>/dev/null; then
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >>~/.zprofile
        fi
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        if ! grep -q '/usr/local/bin/brew shellenv' ~/.zprofile 2>/dev/null; then
            echo 'eval "$(/usr/local/bin/brew shellenv)"' >>~/.zprofile
        fi
        eval "$(/usr/local/bin/brew shellenv)"
    fi

    if command_exists brew; then
        print_success "Homebrew installed successfully"
    else
        print_error "Failed to install Homebrew"
        print_warning "Please install manually and run this script again"
        return 1
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
    sed -n '/# Formulae (Required)/,/# Casks (Required)/p' "$brewfile" | grep -E "^brew " >>"$temp_brewfile" || true
    sed -n '/# Casks (Required)/,/# Optional/p' "$brewfile" | grep -E "^cask " >>"$temp_brewfile" || true

    # Process optional packages
    print_info "Select optional packages to install..."

    local in_optional=false
    local current_tap=""

    while IFS= read -r line <&3; do
        # Check if we've reached the optional section
        if [[ "$line" == "# Optional Formulae & Casks" || "$line" == "# Optional Formulae" ]]; then
            in_optional=true
            continue
        fi

        # Skip empty lines and comments (but not after entering optional section check)
        if [[ "$in_optional" == false ]]; then
            [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        fi

        # In optional section, skip empty lines and comments
        [[ -z "$line" ]] && continue
        [[ "$line" =~ ^[[:space:]]*#.*$ ]] && continue

        if [[ "$in_optional" == true ]]; then
            # Handle tap declarations
            if [[ "$line" =~ ^tap[[:space:]]\"([^\"]+)\" ]]; then
                current_tap="$line"
                continue
            fi

            # Handle brew/cask lines
            if [[ "$line" =~ ^(brew|cask)[[:space:]]\"([^\"]+)\" ]]; then
                local package_name="${BASH_REMATCH[2]}"

                if ask_yes_no "Install $package_name?"; then
                    # Add the tap if there is one
                    if [[ -n "$current_tap" ]]; then
                        echo "$current_tap" >>"$temp_brewfile"
                        current_tap=""
                    fi
                    echo "$line" >>"$temp_brewfile"
                else
                    # User declined, clear any pending tap
                    current_tap=""
                fi
            fi
        fi
    done 3<"$brewfile"

    # Check if there are any packages to install
    if [[ -s "$temp_brewfile" ]]; then
        print_info "Installing selected packages..."
        brew bundle --file="$temp_brewfile"
        print_success "Homebrew packages installed"
    else
        print_warning "No packages selected for installation"
    fi

    rm "$temp_brewfile"
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

    local all_packages=("${required_packages[@]}" ${optional_packages[@]+"${optional_packages[@]}"})
    local total=${#all_packages[@]}
    local current=0

    print_info "Installing npm packages..."
    for package in "${all_packages[@]}"; do
        current=$((current + 1))
        if npm install -g "$package" &>/dev/null; then
            progress_bar "$current" "$total"
        else
            echo ""
            print_warning "Failed to install $package"
            progress_bar "$current" "$total"
        fi
    done

    echo ""
    print_success "Node.js global packages installation complete"
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
        read -r -p "$(echo -e "${YELLOW}?${NC} Enter your dotfiles repository URL: ")" repo_url </dev/tty
    fi

    if [[ -z "$repo_url" ]]; then
        print_error "No repository URL provided"
        return 1
    fi

    if git clone "$repo_url" "$dotfiles_dir"; then
        print_success "Dotfiles cloned to $dotfiles_dir"
    else
        print_error "Failed to clone repository"
        return 1
    fi
}

setup_symlinks() {
    print_step "Setting up symlinks with GNU Stow"

    local dotfiles_dir="$HOME/.dotfiles"

    if [[ ! -d "$dotfiles_dir" ]]; then
        print_error "Dotfiles directory not found at $dotfiles_dir"
        return 1
    fi

    cd "$dotfiles_dir" || {
        print_error "Failed to change to dotfiles directory"
        return 1
    }

    # Get list of directories to stow (excluding non-config directories)
    local config_dirs=()
    local dir
    while IFS= read -r dir; do
        [[ -n "$dir" ]] && config_dirs+=("$dir")
    done < <(find . -maxdepth 1 -type d ! -name '.' ! -name '.git' ! -name 'install' ! -name 'backgrounds' ! -name 'fonts' ! -name 'dev' -exec basename {} \;)

    if [[ ${#config_dirs[@]} -eq 0 ]]; then
        print_warning "No configuration directories found to stow"
        return 0
    fi

    for dir in "${config_dirs[@]}"; do
        if ask_yes_no "Symlink $dir configuration?" </dev/tty; then
            if stow -v "$dir" 2>&1 | grep -qv "BUG in find_stowed_path"; then
                print_success "Symlinked $dir"
            else
                print_warning "Failed to symlink $dir (conflicts may exist)"
            fi
        fi
    done

    cd "$HOME" || return 0
}

install_fonts() {
    print_step "Installing fonts"

    local fonts_dir="$HOME/.dotfiles/fonts"

    if [[ ! -d "$fonts_dir" ]]; then
        print_warning "Fonts directory not found, skipping font installation"
        return 0
    fi

    if ! ask_yes_no "Install fonts from fonts directory?" </dev/tty; then
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
        if ask_yes_no "Set zsh as default shell?" </dev/tty; then
            print_info "You may be prompted for your password"
            if chsh -s "$(which zsh)"; then
                print_success "Default shell changed to zsh"
            else
                print_warning "Failed to change shell (you may need to do this manually)"
            fi
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

    if ! ask_yes_no "Do you want to continue?" "y" </dev/tty; then
        print_info "Installation cancelled"
        exit 0
    fi

    # Calculate total steps
    TOTAL_STEPS=8

    print_header "Starting Installation"

    # Step 1: Xcode CLI Tools
    install_xcode_cli_tools || {
        print_error "Cannot continue without Xcode Command Line Tools"
        exit 1
    }

    # Step 2: Homebrew
    install_homebrew || {
        print_error "Cannot continue without Homebrew"
        exit 1
    }

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
    echo ""
    echo -e "${BOLD}Installed to:${NC} $HOME/.dotfiles"
    echo ""

    if ask_yes_no "Would you like to restart your shell now?" "y" </dev/tty; then
        exec zsh -l
    fi
}

# Run main function
main "$@"
