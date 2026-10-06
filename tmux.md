# Keybinds

## General

- Ctrl-b r — reload config
- Ctrl-b d — detach session
- Ctrl-b : — command prompt
- Ctrl-b ? — list all keybinds

## Sessions

- tmux new -s <name> / tmux attach -t <name> / tmux ls
- Ctrl-b s — interactive session list, pick one
- Ctrl-b ( / Ctrl-b ) — previous / next session
- Ctrl-b L — toggle to last session
- Ctrl-b :switch-client -t <name> — jump to session by name
- tmux kill-session -t <name> / tmux kill-server — from shell
- tmux kill-server then e.g. tmux ls — restart server (auto-starts on next command)

## Windows (tabs)

- Ctrl-b c — new window
- Ctrl-b , — rename window
- Ctrl-b n / p — next / previous window
- Ctrl-Shift-Left / Ctrl-Shift-Right — prev / next window, no prefix
- Ctrl-b 0-9 — jump to window by number
- Ctrl-b & — kill window

## Panes (splits)

- Ctrl-b % — vertical split (side by side)
- Ctrl-b " — horizontal split (stacked)
- Ctrl-b h/j/k/l — move left/down/up/right
- Ctrl-b q — show pane numbers, then jump
- Ctrl-b z — zoom/unzoom pane
- Ctrl-b x — kill pane
- Ctrl-b { / } — swap panes
- Ctrl-b Ctrl-arrow — resize pane

## Copy mode (mode-keys vi)

- Ctrl-b [ — enter copy mode
- h/j/k/l, w/b, / ? — navigate / search
- Space — start selection, Enter — copy, q — exit
- v — toggle rectangle selection
- Ctrl-b ] — paste

## Plugins (TPM)

- Ctrl-b I — install
- Ctrl-b U — update
- Ctrl-b Alt-u — uninstall
