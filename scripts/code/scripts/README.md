# Haya Repositories Manager

Small terminal menu app for managing multiple Git repos from one place.

## What it does

- Show Git status across configured repos
- Hard reset all repos to `main`
- Stash + checkout all repos to `main`
- Fuzzy search branch checkout per repo
- Run `make restart` in the Haya parent repo
- Open a repo in a selected code editor
- Show Docker container overview + one-key cleanup actions

---

## Requirements

### Required

- Python 3.8+
- Git

### Feature-dependent

- `fzf` (for branch picker in option 4)
- Docker CLI + running daemon (for option 7)
- Editor CLIs you want to use (`kitty`, `code`, `zed`, etc.)

### Install examples

#### macOS (Homebrew)

```bash
brew install git fzf
# optional
brew install --cask docker
brew install --cask visual-studio-code zed kitty
```

#### Ubuntu/Debian

```bash
sudo apt update
sudo apt install -y git fzf python3
# optional
sudo apt install -y docker.io
```

---

## Configure repositories

Edit the `REPOS` list in:

- [./haya-repos.py](./haya-repos.py)

Use absolute paths or `~` paths.

---

## Make it executable

```bash
chmod +x haya-repos.py
```

Run it directly (adjust path as required):

```bash
./haya-repos.py
```

Or via Python:

```bash
python3 haya-repos.py
```

---

## Optional shell alias

Add to your shell config:

```bash
alias haya='python3 ~/haya-repos.py'
```

Adjust the path to match your local location.

---

## Add a new code editor option

Code editors are defined in `EDITOR_MENU_OPTIONS` and dispatched by function name.

### 1) Add a launcher function

You'll need to write a function with the right launch command for your editor.

In [haya-repos.py](./haya-repos.py), add a function with this signature:

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
