#!/bin/bash
set -e

# Installation script for dotfiles in dev container (Ubuntu)

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Installing dotfiles from: $DOTFILES_DIR"

# Create necessary directories
mkdir -p ~/.config

# Install zsh configuration
if [ -f "$DOTFILES_DIR/zshrc/.zshrc" ]; then
    echo "Installing zsh configuration..."
    cp "$DOTFILES_DIR/zshrc/.zshrc" ~/.zshrc
fi

# Install neovim configuration
if [ -d "$DOTFILES_DIR/nvim/.config/nvim" ]; then
    echo "Installing neovim configuration..."
    cp -r "$DOTFILES_DIR/nvim/.config/nvim" ~/.config/
fi

# Install starship configuration
if [ -f "$DOTFILES_DIR/starship/.config/starship.toml" ]; then
    echo "Installing starship configuration..."
    cp "$DOTFILES_DIR/starship/.config/starship.toml" ~/.config/starship.toml
fi

# Install yazi configuration
if [ -d "$DOTFILES_DIR/yazi/.config/yazi" ]; then
    echo "Installing yazi configuration..."
    cp -r "$DOTFILES_DIR/yazi/.config/yazi" ~/.config/
fi

echo "✓ Dotfiles installation complete!"
