# Dotfiles

## My config files for various applications

I am using GNU Stow to symlink these files from this repository to their appropriate locations in my home directory.

## Installation

To install these dotfiles on a new machine, run the install script. This script will install Homebrew, the necessary packages, and set up the dotfiles using Stow.

```bash


```

## Dev containers

This repo also has an install script to copy some dotfiles into dev containers, which should be run from docker-compose.

Clone the repo and run the ./dev/install-dev.sh script

## TODOs

- [x] write brew file with all my installed packages/apps
- [x] write install script for macOS to install all and stow dotfiles
- [ ] create repo for dev containers for frontend/php development once I have a nice setup
