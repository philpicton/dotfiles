# Dotfiles

## Work version of the dotfiles

This repo contains various configuration files for applications that I use. I am using GNU Stow to symlink these files from a local folder (`~/dotfiles` which I'm tracking in this repo) to their correct location.

This branch (`work-macos`) contains dotfiles used on my work mac (minus any things that could be sensitive)

There are many prerequisites necessary to have these files provide their full functionality, and a lot of the programs that these files configure prefer a particular operating system (by the way). Some don't.

## Installation

Installed Packages (via homebrew)

- gnu stow
- kitty
  - zsh autosuggestions, autocomplete and syntax highlighting
- neovim
  - wl-clipboard
  - lazygit
  - ripgrep
  - fd
  - node
  - @vue/language-server
  - lazydocker
- Firacode Font and the Nerd Font (kitty terminal prefers to use normal font not the nerd patched one.)
- starship
- tmux
- fzf
- yazi
- glow

1. Clone this repo to ~/dotfiles and `cd` into it
2. install the various configs with eg. `stow ghostty`

NB if the folder/config file already exists on the machine you'll get an error.

Watch out for hidden OS files like `.DS_Store` which can add themselves to the dotfiles folders, and the target location. Then when you try to stow to an empty folder, you still get the error.

To prevent this:

```bash
touch ~/.stow-global-ignore && echo '\.DS_Store' >> ~/.stow-global-ignore
```
