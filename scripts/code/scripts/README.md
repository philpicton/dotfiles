# REPO-MAN

> ✨ Haya Repositories Manager ✨

Small terminal menu app for managing multiple Git repos from one place.

Written in Python. Vibe coded with 🧡

## What it does

- Show number of open PRs with your review requested
- Show number of unread github notifications
- Show the days upcoming calendar events (MacOS calendar)
- Show Git status across configured repos
- Hard reset all repos to `main`
- Stash + checkout all repos to `main`
- Fuzzy search branch checkout per repo
- Run the Haysto-v2 make/app commands
- Open a repo directly in `nvim` in a new Kitty tab
- Open `haysto-v2-api`, `haysto-v2-collect`, `haysto-v2-create`, and `haysto-v2-lib_shared` together in separate Kitty tabs
- Show Docker container overview + one-key cleanup actions
- Run the multi-repo branch checkout workflow as a standalone Go CLI

---

## 1. Requirements

### Required

- Python 3.8+

### Feature-dependent

- `fzf` (for branch picker in option 4)
- Go toolchain (for the standalone `branch-checkout` CLI)
- Docker CLI + running daemon (for option 5 and option 7)
- `kitty` in your `PATH` (option 6 launches `nvim` inside Kitty tabs)
- Github CLI (gh) installed and logged in (to show requested reviews and unread notifications)
- `icalBuddy` installed (to show upcoming calendar events on MacOS)

---

## 2. Configure repositories and notifications

Edit the `REPOS` list in:

- [./repo-man.py](./repo-man.py)

Add in what repos you want to manage, with their paths on your system. Use absolute paths or `~` paths.

Get the uuid of your work calendar and place it in the `ICAL_CALENDAR_IDS` constant near the top of `repo-man.py`.

```bash
# lists your mac calendars
icalbuddy calendars
```

---

## 3. Make it executable

```bash
chmod +x repo-man.py
```

Run it directly (adjust path as required):

```bash
./repo-man.py
```

Or via Python:

```bash
python3 repo-man.py
```

---

## 4. Optional shell alias

Add to your shell config (`.zshrc` etc):

```bash
alias haya='python3 ~/repo-man.py'
```

Adjust the path to match your local location.

Then type 'haya' to launch.

---

## 5. Open repos in Kitty

Option **6** always opens the selected repo in `nvim` in a new Kitty tab.

Inside that menu, press **a** to open these repos together in separate tabs, in this order:

1. `haysto-v2-api`
2. `haysto-v2-collect`
3. `haysto-v2-create`
4. `haysto-v2-lib_shared`

---

## Notes

- Main menu supports single-key input (no Enter).
- Press `q` or `Esc` in most submenus to go back.
- Press `Esc` at main menu to quit.
