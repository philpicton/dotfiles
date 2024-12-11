# Dotfiles

## Work version of the dotfiles

This repo contains various configuration files for applications that I use. I am using GNU Stow to symlink these files from a local folder (`~/dotfiles` which I'm tracking in this repo) to their correct location.

This branch (`work-macos`) contains dotfiles used on my work mac (minus any things that could be sensitive)

There are many prerequisites necessary to have these files provide their full functionality, and a lot of the programs that these files configure prefer a particular operating system (by the way). Some don't.

## Installation

Installed Packages (via homebrew)

- gnu stow
- kitty
  - zsh autosuggestions and syntax highlighting
- neovim
  - wl-clipboard
  - lazygit
  - ripgrep
  - fd
  - node
  - @vue/language-server
- Firacode Nerd Font
- starship
- tmux
- fzf
- yazi
  - glow
