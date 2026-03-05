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
- Run the make commands in Haysto-v2 repo
- Open a repo in a selected code editor
- Show Docker container overview + one-key cleanup actions

---

## 1. Requirements

### Required

- Python 3.8+

### Feature-dependent

- `fzf` (for branch picker in option 4)
- Docker CLI + running daemon (for option 7)
- Editor CLIs you want to use (`kitty`, `code`, `zed`, etc.)
- Github CLI (gh) installed and logged in (to show requested reviews and unread notifications)
- `icalBuddy` installed (to show upcoming calendar events)

---

## 2. Configure repositories and notifications

Edit the `REPOS` list in:

- [./repo-man.py](./repo-man.py)

Add in what repos you want to manage, with their paths on your system. Use absolute paths or `~` paths.

Get the uuid of your work calendar and place it in the ICAL_CALENDAR_IDS const near line 28.

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
./haya-repos.py
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

## Add a new code editor option

Code editors are defined in `EDITOR_MENU_OPTIONS` and dispatched by function name.

### 1) Add a launcher function

You'll need to write a function with the right launch command for your editor.

In [repo-man.py](./repo-man.py), add a function with this signature:

```python
def open_repo_in_example(repo_path: Path) -> Tuple[int, str]:
    return run_editor_command(['example-editor-cli-command', str(repo_path)], "Opened in Example Editor")
```

### 2) Add an entry to `EDITOR_MENU_OPTIONS`

```python
{
    'key': '4',
    'label': 'Example Editor',
    'function_name': 'open_repo_in_example',
}
```

That is all you need. The menu is rendered dynamically and the function is called automatically.

---

## Notes

- Main menu supports single-key input (no Enter).
- Press `q` or `Esc` in most submenus to go back.
- Press `Esc` at main menu to quit.
