# Dotfiles

## My config files for various applications

I am using GNU Stow to symlink these files from this repository to their appropriate locations in my home directory.

## Installation

Installed Packages (This branch for macOS)

- gnu stow
- kitty
- zsh autosuggestions
  = zsh syntax highlighting
- Ghostty
- neovim
  - wl-clipboard
  - lazygit
  - ripgrep
  - fd
  - fzf
  - treesitter-cli
  - c compiler (Xcode command line tools on macOS)
  - Node Packages for neovim LSP support
    - node & npm
    - neovim npm package
    - @vue/language-server
    - typescript
    - @typescript/language-server

- Firacode Nerd Font
- starship
- tmux
- yazi
- lazydocker
- sketchybar
- Aerospace
- Docker
  ... plus all my usual

## Dev containers

This repo also has an install script to copy some dotfiles into dev containers, which will be run from docker-compose.

Clone the repo and run the install script

## TODOs

- [ ] write brew file with all my installed packages/apps
- [ ] write install script for macOS to install all and stow dotfiles
- [ ] create repo for dev containers for frontend/php development once I have a nice setup
