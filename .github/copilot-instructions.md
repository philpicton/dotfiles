# Copilot Instructions

This is a personal macOS dotfiles repository managed with **GNU Stow**. Configs are symlinked from this repo into `$HOME` — each top-level directory (except `install/`, `backgrounds/`, `fonts/`, `dev/`) is a Stow package.

## Setup & Installation

```bash
# Full install (macOS, fresh machine)
bash <(curl -fsSL https://raw.githubusercontent.com/philpicton/dotfiles/main/install/install.sh) https://github.com/philpicton/dotfiles

# Manually stow a single package (from repo root)
stow <package>          # e.g. stow nvim, stow zshrc, stow ghostty

# Dev container setup (copies instead of symlinks)
bash dev/install-dev.sh
```

There are no build, test, or lint commands — this is a configuration-only repository.

## Architecture

**Stow symlink layout:** Files are stored as `<package>/.config/app-name/config-file` or `<package>/.<dotfile>` and symlinked to the same relative path under `$HOME`. For example:
- `nvim/.config/nvim/init.lua` → `~/.config/nvim/init.lua`
- `zshrc/.zshrc` → `~/.zshrc`
- `misc/.gitconfig` → `~/.gitconfig`

**Two install modes:**
- macOS: GNU Stow symlinks (live-updating from the repo)
- Dev containers (`dev/install-dev.sh`): direct copy to `~/.config` (no symlink dependency)

**Theme:** Catppuccin Mocha is used consistently across bat, delta, kitty, tmux, starship, lazygit, and Neovim.

## Key Conventions

**install/install.sh** uses `set -euo pipefail`, colored output helpers (`print_step`, `print_success`, etc.), and a `command_exists()` guard. Follow these patterns when modifying it.

**Brewfile** (`install/Brewfile`) has a `# Required` section and an `# Optional` section — the install script parses these sections to offer interactive selection for optional packages. Keep this separation when adding entries.

**Stow exclusions:** The install script skips `install/`, `backgrounds/`, `fonts/`, `dev/`, and `.git` when running Stow. If adding a new package directory that shouldn't be stowed, update the exclusion list in `install/install.sh`.

**Architecture-aware paths:** `zshrc/.zshrc` and `install/install.sh` detect Apple Silicon (`arm64`) vs Intel to set the correct Homebrew prefix (`/opt/homebrew` vs `/usr/local`). Preserve this pattern when adding shell config or install steps.

**Neovim** uses [LazyVim](https://lazyvim.github.io/) as the base framework with [lazy.nvim](https://github.com/folke/lazy.nvim) as plugin manager. Plugins are in `nvim/.config/nvim/lua/plugins/` — one file per concern. Options are in `lua/config/options.lua` (note: `tabstop=4`).

**zshrc** is intentionally a single flat file (`zshrc/.zshrc`) — no modular sourcing. Keep it that way unless there's a strong reason to split.

**scripts/code/scripts/repo-man.py** is a 1500-line Python TUI for managing Haya org repos. It's launched from Neovim via `<leader>hh` and the `hh`/`haya` shell aliases. It uses threading + TTL caching for GitHub API and macOS Calendar calls — maintain those patterns when extending it.

## Copilot Behaviour

**Code style:** Write clear, readable code. Follow the conventions already present in the file being edited (indentation, quoting style, naming, etc.).

**Comments:** Add comments to explain non-obvious logic or anything that may be unfamiliar — config DSL quirks, shell edge cases, plugin-specific APIs. Don't comment self-explanatory code.

**Third-party dependencies:** When configuring or modifying a tool, refer to its man page or latest official documentation rather than relying on prior knowledge. Option names and defaults change across versions.

**Scope:** Only make changes that were explicitly requested. If you spot something unrelated that looks worth fixing, ask first before touching it.

**Git:** Only use read-only git commands (`git log`, `git diff`, `git status`, `git show`, `git branch`, etc.). Never run anything that writes to the index, working tree, stash, or remote (no `add`, `commit`, `push`, `reset`, `checkout`, `merge`, `rebase`, `stash`, etc.).
