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
- Run the active group's Haysto-v2 make/app commands
- Open a repo in a selected code editor
- Show Docker container overview + one-key cleanup actions
- Create and switch full multi-repo worktree groups
- Initialise non-main worktrees and bootstrap their isolated databases

---

## 1. Requirements

### Required

- Python 3.8+

### Feature-dependent

- `fzf` (for branch picker in option 4)
- Docker CLI + running daemon (for option 5, option 7, and worktree stack management)
- Node.js (for the Haysto node-modules manager used by make/init and worktree initialisation)
- Editor CLIs you want to use (`kitty`, `code`, `zed`, etc.)
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

## 5. Add a new code editor option

Code editors are defined in `EDITOR_MENU_OPTIONS` in `repo-man.py`.

### 1) Add a launcher function

You'll need to write a function with the right launch command for your editor.

In [repo_man/shell.py](./repo_man/shell.py), add a function with this signature:

```python
def open_repo_in_example(repo_path: Path) -> Tuple[int, str]:
    return run_editor_command(['example-editor-cli-command', str(repo_path)], "Opened in Example Editor")
```

It needs to begin with `open_repo_in_`.

### 2) Add an entry to `EDITOR_MENU_OPTIONS`

```python
{
    'key': '4',
    'label': 'Example Editor',
    'function_name': 'open_repo_in_example',
}
```

---

## 6. Worktree groups

This is an optional feature, to create and manage multiple worktree groups with separate branches, local files, and Docker containers. Helpful if you need to work on multiple things concurrently, or have different database setups, or want to compare your work against `main` without switching branches.

Repo-man treats a worktree group as a full set of all configured repos under one named folder.

- `main` is the maintained default group at `ROOTDIR/<repos>`
- each extra group lives at `ROOTDIR/<group-name>/<repos>`
- new groups are created from each repo's `main` branch on a new branch named `worktree-<group>/main` by default
- You can't checkout the same branch in multiple worktrees, so we create a new one.
- repo-man copies only allowlisted gitignored local config files into the new worktree, such as `.env`, `.env.*`, and local nginx certs under `docker/nginx/certificates/`, then recreates the shared-lib symlinks

### Docker behavior

- `main` keeps the original docker compose project naming
- non-main groups use a compose project name prefixed with the group name, so they get their own containers and volumes
- switching groups brings down any other running worktree stack first
- if the target group is already initialised, switching starts it with the `local` compose profile so non-main groups get their own local-profile services too, including things like nginx, MySQL, mail, redis, and supervisor when the Haysto compose file defines them
- if the target group is still fresh, switching leaves the stack stopped so **Initialise active worktree** can follow the same order as `make init`: build, install dependencies, then start containers

### Initialising a new worktree

New worktree groups are created with isolated repos, local files, and docker naming, but they are **not** fully bootstrapped yet.

The recommended flow is:

1. Create the worktree group.
2. Switch to it.
3. Open the worktrees menu and run **Initialise active worktree**.
4. Open option **5** and run **Initialise current worktree database**.
5. Then you can work with the new worktree as you would normally, without interfering with the main group.

### Important setup note

Creating a worktree group does **not** initialise its database contents by itself.

- the worktrees menu's **Initialise active worktree** action runs the worktree-safe equivalent of `make init`
- option **5** adds **Initialise current worktree database** for non-main groups, which runs the migrations, seed step, and permission reseed needed to get the app working
- regular `make init` is hidden from option **5** when a non-main group is active because Composer's git-hook setup is not worktree-safe inside the mounted containers

---

## Notes

- Main menu supports single-key input (no Enter).
- Press `q` or `Esc` in most submenus to go back.
- Press `Esc` at main menu to quit.
