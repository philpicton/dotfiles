# Phils Neovim Config

> These are my (current) Neovim dotfiles. They are based on [Lazyvim](https://github.com/LazyVim/LazyVim), a starter config which provides a full featured IDE. I have used this starter config, and added some bits and pieces to make it suitable for front end (Vue/Javascript) development.

## Installation

Prerequisites (on Mac):

```bash
brew install neovim ripgrep fd gnu-sed

npm install -g neovim @volar/vue-language-server
```

Then clone this repo into `~/.config/nvim`.

Don't forget to install any Language Servers you need, for example:

':TSInstall vue-language-server'

If you are doing Vue development, don't install a Typescript Language Server. The Volar (vue language server) is set up to handle TS, and the TS server will not understand `.vue` files.
