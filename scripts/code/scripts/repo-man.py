#!/usr/bin/env python3
"""
REPO MAN
Haya Repositories Manager - TUI for managing git repositories

"""

import os
import shutil
import subprocess
import sys
import tty
import termios
import datetime
import getpass
import json
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# CUSTOMISE THE BELOW VALUES ------------------------------------------------

# Calendar UUIDs to include in the notifications panel.
# Add multiple UUIDs as separate strings in the list.
# Find yours by running: icalBuddy calendars
ICAL_CALENDAR_IDS = [
    '3E7B91E3-B0EE-4A63-8856-3FED7A55F71D',
]

# The folder where you store the repos, and any worktrees created by this script. 
# Customise this to your preferred location.
ROOTDIR = "~/code/haya"

# Main Repository folder names relative to ROOTDIR. 
# haysto-v2 must be first, and be found at ROOTDIR/haysto-v2 for the script to work correctly. 
# add any others you want to manage at the end.
REPOS = [
    "haysto-v2",
    "haysto-v2/haysto-v2-api",
    "haysto-v2/haysto-v2-collect",
    "haysto-v2/haysto-v2-create",
    "haysto-v2/lib/js/haysto-v2-lib_shared",
    "enquiry-form",
]
# ---------------------------------------------------------------------------

# Expand paths and convert to absolute paths
ROOT_PATH = Path(ROOTDIR).expanduser().resolve()
REPO_RELATIVE_PATHS = [Path(repo) for repo in REPOS]
REPO_PATHS = [(ROOT_PATH / repo).resolve() for repo in REPO_RELATIVE_PATHS]

# Worktree group state
MAIN_WORKTREE_GROUP = 'main'
MAIN_WORKTREE_FOLDER_NAME = 'haysto-v2'
RESERVED_WORKTREE_GROUP_NAMES = {MAIN_WORKTREE_GROUP, MAIN_WORKTREE_FOLDER_NAME}
WORKTREE_STATE_FILE = ROOT_PATH / '.repo-man-worktrees.json'
_active_worktree_group: str = MAIN_WORKTREE_GROUP
_startup_notice: Optional[str] = None

# ANSI color codes for terminal output
ORANGE = '\033[38;5;208m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
DIM = '\033[2m'
RESET = '\033[0m'

# ---------------------------------------------------------------------------
# Background data cache
# Fetches GitHub and calendar info in background threads so the menu never
# blocks waiting for network / subprocess calls.
# ---------------------------------------------------------------------------
_LOADING = object()   # sentinel: fetch not yet complete
_CACHE_TTL = 60       # seconds before a cached value is considered stale
_show_notifications: bool = False  # toggled by option 8

_cache: dict = {
    'review_count':       _LOADING,
    'notification_count': _LOADING,
    'calendar_events':    _LOADING,
    'fetched_at':         0.0,
    'is_fetching':        False,
}
_cache_lock = threading.Lock()


def _run_cache_fetch() -> None:
    """Fetch all dashboard data concurrently and write results into the cache."""
    with _cache_lock:
        if _cache['is_fetching']:
            return
        _cache['is_fetching'] = True

    results: dict = {}

    def _reviews():
        results['review_count'] = get_github_review_requests()

    def _notifications():
        results['notification_count'] = get_github_unread_notifications()

    def _calendar():
        results['calendar_events'] = get_todays_calendar_events()

    try:
        threads = [
            threading.Thread(target=_reviews, daemon=True),
            threading.Thread(target=_notifications, daemon=True),
            threading.Thread(target=_calendar, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        with _cache_lock:
            _cache.update(results)
            _cache['fetched_at'] = time.monotonic()
    finally:
        with _cache_lock:
            _cache['is_fetching'] = False


def refresh_cache_in_background(force: bool = False) -> None:
    """Kick off a background refresh unless one is already running or data is fresh."""
    with _cache_lock:
        age = time.monotonic() - _cache['fetched_at']
        if not force and _cache['fetched_at'] > 0 and age < _CACHE_TTL:
            return
        if _cache['is_fetching']:
            return

    threading.Thread(target=_run_cache_fetch, daemon=True).start()

# You can add other code editors here, just write a function to open your editor.
EDITOR_MENU_OPTIONS = [
    {
        'key': '1',
        'label': 'NVIM in new Kitty tab',
        'function_name': 'open_repo_in_kitty_tab',
    },
    {
        'key': '2',
        'label': 'VS Code',
        'function_name': 'open_repo_in_vscode',
    },
    {
        'key': '3',
        'label': 'Zed',
        'function_name': 'open_repo_in_zed',
    },
]
# You can add other cli commands here, use letters if you run out of numbers!
MAKE_COMMANDS = [
    {'key': '1', 'label': 'Restart docker containers, manage node modules', 'command': 'make restart'},
    {'key': '2', 'label': 'Rebuild containers and app', 'command': 'make init'},
    {'key': '3', 'label': 'Containers down', 'command': 'make down'},
    {'key': '4', 'label': 'Artisan migrate', 'command': 'docker compose exec haysto-api php artisan migrate'},
    {'key': '5', 'label': 'Update permissions', 'command': 'make update_permissions'},
    {'key': '6', 'label': 'Bulk seed cases', 'command': 'make cases'},
    {'key': '7', 'label': 'Seed a case at a particular stage', 'command': 'make case'},
    {'key': '8', 'label': 'Shell into haysto-v2-api container', 'command': 'docker compose exec haysto-api bash'},
]

def clear_screen():
    """Clear the terminal screen."""
    os.system('clear')


def wait_for_key():
    """Wait for user to press any key to continue."""
    input("\n\nPress Enter to return to menu...")


def get_single_char():
    """Read a single character from stdin without requiring Enter."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def run_git_command(repo_path: Path, command: List[str], show_output: bool = True) -> Tuple[int, str, str]:
    """
    Run a git command in a specific repository.
    
    Args:
        repo_path: Path to the repository
        command: Git command as a list (e.g., ['git', 'status'])
        show_output: Whether to print output in real-time
    
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        if show_output:
            # Run with real-time output
            process = subprocess.Popen(
                command,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            if stdout:
                print(stdout, end='')
            if stderr:
                print(stderr, end='', file=sys.stderr)
            return process.returncode, stdout, stderr
        else:
            # Run silently and capture output
            result = subprocess.run(
                command,
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def normalize_branch_selection(selected_branch: str) -> str:
    """Normalize branch output from `git branch --all` style lines.

    Examples:
      '* main' -> 'main'
      '  remotes/origin/feature-x' -> 'feature-x'
      '  feature-x' -> 'feature-x'
    """
    branch = selected_branch.strip()

    if branch.startswith('* '):
        branch = branch[2:].strip()

    # Match behavior from .zshrc gch function:
    # sed "s/.* //" | sed "s#remotes/[^/]*/##"
    if ' ' in branch:
        branch = branch.split()[-1]

    if branch.startswith('remotes/'):
        parts = branch.split('/', 2)
        if len(parts) == 3:
            branch = parts[2]

    return branch


def pick_source_branch_with_fzf(repo_path: Path, current_branch: str) -> Tuple[bool, str]:
    """Open fzf branch picker pre-seeded with the current branch as the default query.

    Returns:
        (selected, branch_name)
        - selected=False indicates skip/cancel (e.g. Esc pressed)
    """
    returncode, branches, stderr = run_git_command(
        repo_path,
        ['git', 'branch', '--all'],
        show_output=False
    )

    if returncode != 0:
        raise RuntimeError(stderr.strip() or "Failed to list branches")

    branch_lines = [line for line in branches.splitlines() if 'HEAD' not in line]
    if not branch_lines:
        raise RuntimeError("No branches available")

    try:
        fzf_result = subprocess.run(
            [
                'fzf',
                '--height', '40%',
                '--reverse',
                '--prompt', f'{repo_path.name}> ',
                '--header', 'Select source branch (current branch pre-selected, Esc to skip)',
                '--bind', 'esc:abort',
                '--query', current_branch,
            ],
            input='\n'.join(branch_lines),
            capture_output=True,
            text=True,
            cwd=repo_path
        )
    except FileNotFoundError as e:
        raise RuntimeError("fzf not found. Please install fzf to use this option.") from e

    if fzf_result.returncode != 0:
        return False, ''

    selected_line = fzf_result.stdout.strip()
    if not selected_line:
        return False, ''

    branch_name = normalize_branch_selection(selected_line)
    if not branch_name:
        return False, ''

    return True, branch_name


def _input_with_default(prompt: str, default: str) -> str:
    """Prompt for text input, pre-populating the buffer with *default*.

    The user can edit or clear the pre-populated text.  Pressing Enter
    immediately accepts the default.  Falls back to plain input() when
    readline is unavailable.
    """
    try:
        import readline

        def _hook() -> None:
            readline.insert_text(default)
            readline.redisplay()

        readline.set_pre_input_hook(_hook)
        try:
            return input(prompt)
        finally:
            readline.set_pre_input_hook(None)
    except ImportError:
        return input(prompt)


def pick_branch_with_fzf(repo_path: Path) -> Tuple[bool, str]:
    """Open fzf branch picker for a repository.

    Returns:
        (selected, branch_name)
        - selected=False indicates skip/cancel (e.g. Esc pressed)
    """
    returncode, branches, stderr = run_git_command(
        repo_path,
        ['git', 'branch', '--all'],
        show_output=False
    )

    if returncode != 0:
        raise RuntimeError(stderr.strip() or "Failed to list branches")

    # filter out HEAD references
    branch_lines = [line for line in branches.splitlines() if 'HEAD' not in line]
    if not branch_lines:
        raise RuntimeError("No branches available")

    try:
        fzf_result = subprocess.run(
            [
                'fzf',
                '--height', '40%',
                '--reverse',
                '--prompt', f'{repo_path.name}> ',
                '--header', 'Select branch (Esc to keep current branch)',
                '--bind', 'esc:abort'
            ],
            input='\n'.join(branch_lines),
            capture_output=True,
            text=True,
            cwd=repo_path
        )
    except FileNotFoundError as e:
        raise RuntimeError("fzf not found. Please install fzf to use this option.") from e

    # Esc / cancel => non-zero return code, treat as skip
    if fzf_result.returncode != 0:
        return False, ''

    selected_line = fzf_result.stdout.strip()
    if not selected_line:
        return False, ''

    branch_name = normalize_branch_selection(selected_line)
    if not branch_name:
        return False, ''

    return True, branch_name


def run_editor_command(command: List[str], success_message: str) -> Tuple[int, str]:
    """Run an editor command and return (exit_code, message)."""
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            error_message = (result.stderr or result.stdout or '').strip()
            return result.returncode, error_message
        return 0, success_message
    except FileNotFoundError as e:
        return 1, f"Required command not found: {e}"
    except Exception as e:
        return 1, str(e)


def run_command(command: List[str]) -> Tuple[int, str, str]:
    """Run a shell command and return (return_code, stdout, stderr)."""
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def run_command_in_dir(command: List[str], cwd: Path) -> Tuple[int, str, str]:
    """Run a command in a specific directory and capture output."""
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def get_repo_paths_for_group(group_name: str) -> List[Path]:
    """Return repository paths for a worktree group."""
    if group_name == MAIN_WORKTREE_GROUP:
        return REPO_PATHS
    group_root = ROOT_PATH / group_name
    return [(group_root / repo).resolve() for repo in REPO_RELATIVE_PATHS]


def get_active_repo_paths() -> List[Path]:
    """Return repository paths for the currently active worktree group."""
    return get_repo_paths_for_group(_active_worktree_group)


def get_parent_repo_path_for_group(group_name: str) -> Path:
    """Return the parent repo path used for make/docker actions for a group."""
    return get_repo_paths_for_group(group_name)[0]


def get_active_parent_repo_path() -> Path:
    """Return the parent repo path used for make/docker actions for active group."""
    return get_parent_repo_path_for_group(_active_worktree_group)


def validate_worktree_group_name(name: str) -> Tuple[bool, str]:
    """Validate a worktree group folder name for macOS/Linux-safe usage."""
    if not name:
        return False, "Group name cannot be empty"
    if name in RESERVED_WORKTREE_GROUP_NAMES:
        return False, "Group name is reserved"
    if name in ('.', '..'):
        return False, "Group name is invalid"
    if '/' in name or '\\' in name:
        return False, "Group name cannot contain path separators"

    for ch in name:
        if not (ch.isalnum() or ch in ('-', '_', '.')):
            return False, "Use only letters, numbers, dash, underscore, or dot"

    return True, ""


def get_worktree_paths_for_repo(canonical_repo_path: Path) -> Tuple[bool, Set[Path], str]:
    """Return all known worktree paths for a canonical repository."""
    if not canonical_repo_path.exists():
        return False, set(), f"Canonical repo missing: {canonical_repo_path}"

    returncode, stdout, stderr = run_command_in_dir(
        ['git', 'worktree', 'list', '--porcelain'],
        canonical_repo_path
    )
    if returncode != 0:
        err = (stderr or stdout or '').strip()
        return False, set(), err or 'Failed to list git worktrees'

    worktrees: Set[Path] = set()
    for line in stdout.splitlines():
        if line.startswith('worktree '):
            wt_path = line[len('worktree '):].strip()
            if wt_path:
                worktrees.add(Path(wt_path).expanduser().resolve())

    return True, worktrees, ''


def validate_worktree_group(group_name: str) -> Tuple[bool, str]:
    """Strictly validate that a group contains all expected repo worktrees."""
    if group_name == MAIN_WORKTREE_GROUP:
        return True, ''

    group_root = ROOT_PATH / group_name
    if not group_root.exists() or not group_root.is_dir():
        return False, f"{group_name}: group folder is missing"

    for repo_rel in REPO_RELATIVE_PATHS:
        canonical_repo = (ROOT_PATH / repo_rel).resolve()
        target_repo = (group_root / repo_rel).resolve()

        if not target_repo.exists():
            return False, f"{group_name}: missing {repo_rel}"
        if not (target_repo / '.git').exists():
            return False, f"{group_name}: {repo_rel} is not a git worktree folder"

        ok, paths, err = get_worktree_paths_for_repo(canonical_repo)
        if not ok:
            return False, f"{group_name}: {repo_rel} worktree check failed ({err})"
        if target_repo not in paths:
            return False, f"{group_name}: {repo_rel} is not registered as a worktree"

    return True, ''


def discover_worktree_groups() -> Tuple[List[str], Dict[str, str]]:
    """Discover strict-valid worktree groups and invalid candidates under ROOTDIR."""
    valid_groups: List[str] = [MAIN_WORKTREE_GROUP]
    invalid_groups: Dict[str, str] = {}

    if not ROOT_PATH.exists() or not ROOT_PATH.is_dir():
        return valid_groups, invalid_groups

    top_level_repo_roots = {repo.parts[0] for repo in REPO_RELATIVE_PATHS if repo.parts}

    for child in ROOT_PATH.iterdir():
        if not child.is_dir():
            continue

        name = child.name
        if name in top_level_repo_roots:
            continue
        if name.startswith('.'):
            continue
        # Skip directories whose names couldn't be group names (e.g. node_modules)
        name_ok, _ = validate_worktree_group_name(name)
        if not name_ok:
            continue

        is_valid, reason = validate_worktree_group(name)
        if is_valid:
            valid_groups.append(name)
        else:
            invalid_groups[name] = reason

    valid_groups = [MAIN_WORKTREE_GROUP] + sorted(
        [group for group in valid_groups if group != MAIN_WORKTREE_GROUP]
    )
    return valid_groups, invalid_groups


def save_active_worktree_group(group_name: str) -> None:
    """Persist active worktree group to disk."""
    try:
        WORKTREE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        WORKTREE_STATE_FILE.write_text(
            json.dumps({'active_group': group_name}, indent=2),
            encoding='utf-8'
        )
    except Exception:
        # Non-fatal. State persistence should not break the TUI.
        pass


def load_active_worktree_group() -> str:
    """Load persisted active worktree group from disk."""
    if not WORKTREE_STATE_FILE.exists():
        return MAIN_WORKTREE_GROUP

    try:
        data = json.loads(WORKTREE_STATE_FILE.read_text(encoding='utf-8'))
        group_name = str(data.get('active_group', MAIN_WORKTREE_GROUP))
        return group_name
    except Exception:
        return MAIN_WORKTREE_GROUP


def get_group_with_running_docker_stack(groups: List[str]) -> Optional[str]:
    """Best-effort detection of a group with running compose services."""
    if shutil.which('docker') is None:
        return None

    for group in groups:
        repo_root = get_parent_repo_path_for_group(group)
        if not repo_root.exists():
            continue

        returncode, stdout, _ = run_command_in_dir(
            ['docker', 'compose', 'ps', '-q'],
            repo_root
        )
        if returncode == 0 and stdout.strip():
            return group

    return None


def initialise_active_worktree_group() -> None:
    """Load and validate active worktree group from state, then notify on mismatch."""
    global _active_worktree_group
    global _startup_notice

    persisted = load_active_worktree_group()
    valid_groups, _ = discover_worktree_groups()

    if persisted in valid_groups:
        _active_worktree_group = persisted
    else:
        _active_worktree_group = MAIN_WORKTREE_GROUP
        if persisted != MAIN_WORKTREE_GROUP:
            _startup_notice = (
                f"{YELLOW}⚠️  Saved worktree group '{persisted}' is no longer valid. "
                f"Falling back to '{MAIN_WORKTREE_GROUP}'.{RESET}"
            )
        save_active_worktree_group(_active_worktree_group)

    running_group = get_group_with_running_docker_stack(valid_groups)
    if running_group and running_group != _active_worktree_group:
        mismatch = (
            f"{YELLOW}⚠️  Docker appears active for group '{running_group}', "
            f"but repo-man is set to '{_active_worktree_group}'.{RESET}"
        )
        if _startup_notice:
            _startup_notice = f"{_startup_notice}\n{mismatch}"
        else:
            _startup_notice = mismatch


def run_docker_stack_down(repo_root: Path) -> Tuple[bool, str]:
    """Bring docker compose stack down for a repository root."""
    if shutil.which('docker') is None:
        return False, 'Docker CLI not found'
    if not repo_root.exists():
        return False, f'Repo root not found: {repo_root}'

    returncode, stdout, stderr = run_command_in_dir(['docker', 'compose', 'down'], repo_root)
    if returncode != 0:
        return False, (stderr or stdout or 'docker compose down failed').strip()
    return True, (stdout or 'docker compose down complete').strip()


def run_docker_stack_up(repo_root: Path) -> Tuple[bool, str]:
    """Bring docker compose stack up for a repository root."""
    if shutil.which('docker') is None:
        return False, 'Docker CLI not found'
    if not repo_root.exists():
        return False, f'Repo root not found: {repo_root}'

    returncode, stdout, stderr = run_command_in_dir(['docker', 'compose', 'up', '-d'], repo_root)
    if returncode != 0:
        return False, (stderr or stdout or 'docker compose up -d failed').strip()
    return True, (stdout or 'docker compose up -d complete').strip()


def set_active_worktree_group(target_group: str) -> List[str]:
    """Switch active group, docker down/up with warning-only behavior."""
    global _active_worktree_group
    warnings: List[str] = []

    current_root = get_active_parent_repo_path()
    ok, message = run_docker_stack_down(current_root)
    if not ok:
        warnings.append(f"Failed to bring docker down for current group: {message}")

    _active_worktree_group = target_group
    save_active_worktree_group(target_group)

    target_root = get_active_parent_repo_path()
    ok, message = run_docker_stack_up(target_root)
    if not ok:
        warnings.append(f"Failed to bring docker up for new group: {message}")

    return warnings


def truncate_value(value: str, width: int) -> str:
    """Truncate value to a fixed width using an ellipsis when needed."""
    text = (value or '-').replace('\n', ' ').strip()
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + '…'


def print_fixed_width_table(headers: List[str], rows: List[List[str]]) -> None:
    """Print a compact, aligned table that adapts to terminal width."""
    terminal_width = shutil.get_terminal_size((140, 24)).columns

    max_caps = [30, 32, 24, 38, 20]
    min_caps = [14, 12, 12, 12, 10]

    col_widths = []
    for idx, header in enumerate(headers):
        longest_cell = max((len((row[idx] or '-').replace('\n', ' ').strip()) for row in rows), default=0)
        width = max(len(header), longest_cell)
        width = min(width, max_caps[idx])
        width = max(width, min_caps[idx])
        col_widths.append(width)

    def current_total() -> int:
        return sum(col_widths) + (3 * (len(col_widths) - 1))

    shrink_order = [3, 1, 2, 0, 4]  # shrink Ports/Image first
    while current_total() > terminal_width:
        reduced = False
        for idx in shrink_order:
            if col_widths[idx] > min_caps[idx]:
                col_widths[idx] -= 1
                reduced = True
                if current_total() <= terminal_width:
                    break
        if not reduced:
            break

    header_line = ' | '.join(headers[i].ljust(col_widths[i]) for i in range(len(headers)))
    divider_line = '-+-'.join('-' * col_widths[i] for i in range(len(headers)))
    print(header_line)
    print(divider_line)

    for row in rows:
        line = ' | '.join(
            truncate_value(row[i], col_widths[i]).ljust(col_widths[i])
            for i in range(len(headers))
        )
        print(line)


def run_docker_action(action_key: str) -> Tuple[bool, str]:
    """Run a predefined docker maintenance action."""
    action_map = {
        'p': (['docker', 'container', 'prune', '-f'], 'Pruned stopped containers'),
        'i': (['docker', 'image', 'prune', '-f'], 'Pruned dangling images'),
        'n': (['docker', 'network', 'prune', '-f'], 'Pruned unused networks'),
        'v': (['docker', 'volume', 'prune', '-f'], 'Pruned unused volumes'),
        'a': (['docker', 'system', 'prune', '-f'], 'Pruned unused docker resources'),
    }

    if action_key not in action_map:
        return False, 'Unknown action'

    command, success_label = action_map[action_key]
    returncode, stdout, stderr = run_command(command)
    output = (stdout or stderr or '').strip()

    if returncode != 0:
        message = output if output else 'Docker action failed'
        return False, message

    if output:
        return True, f"{success_label}\n{output}"
    return True, success_label


def open_repo_in_kitty_tab(repo_path: Path) -> Tuple[int, str]:
    """Open the repository in nvim in a new kitty tab."""
    cmd = [
        'kitty', '@', 'launch',
        '--type=tab',
        f'--cwd={repo_path}',
        f'--tab-title= {repo_path.name}',
        '--copy-env',
        '--dont-take-focus',
        '--add-to-session',
        '!', 'nvim'
    ]
    return run_editor_command(cmd, "Opened in new kitty tab")


def open_repo_in_vscode(repo_path: Path) -> Tuple[int, str]:
    """Open the repository in VS Code."""
    return run_editor_command(['code', str(repo_path)], "Opened in VS Code")


def open_repo_in_zed(repo_path: Path) -> Tuple[int, str]:
    """Open the repository in Zed."""
    return run_editor_command(['zed', str(repo_path)], "Opened in Zed")


def find_editor_option(choice: str):
    """Find a configured editor option by key."""
    for option in EDITOR_MENU_OPTIONS:
        if option['key'] == choice:
            return option
    return None


def open_repo_in_code_editor(repo_path: Path, function_name: str) -> Tuple[int, str]:
    """Open a repository by calling the configured editor function name."""
    function_name = function_name.strip()
    editor_function = globals().get(function_name)

    if not callable(editor_function):
        return 1, f"Invalid editor function: '{function_name}'"

    try:
        return editor_function(repo_path)
    except Exception as e:
        return 1, str(e)


def select_code_editor_launcher() -> Tuple[bool, str]:
    """Show editor launcher menu and return (selected, launcher)."""
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}SELECT CODE EDITOR{RESET}")
    print("~" * 60)
    print()
    for option in EDITOR_MENU_OPTIONS:
        print(f"  {option['key']}. {option['label']}")
        print()

    print("\nPress number to select launcher")
    print("Press q or Esc to cancel")
    print("\n" + "~" * 60)

    option_keys = [option['key'] for option in EDITOR_MENU_OPTIONS]
    keys_display = '/'.join(option_keys)

    while True:
        print(f"\nSelect launcher ({keys_display}, q, Esc): ", end='', flush=True)
        choice = get_single_char()
        print()

        if choice in ('q', 'Q', '\x1b'):
            return False, ''

        option = find_editor_option(choice)
        if option:
            return True, option['function_name']

        print(f"{RED}✗ Invalid choice. Use {keys_display}, q, or Esc.{RESET}")


def validate_repos() -> bool:
    """
    Check if all repository directories exist.
    
    Returns:
        True if all repos exist, False otherwise
    """
    all_exist = True
    missing_repos = []
    
    for repo_path in REPO_PATHS:
        if not repo_path.exists():
            all_exist = False
            missing_repos.append(str(repo_path))
        elif not (repo_path / '.git').exists():
            all_exist = False
            missing_repos.append(f"{repo_path} (not a git repository)")
    
    if not all_exist:
        print(f"{YELLOW}⚠️  WARNING: Some repositories are missing or invalid:{RESET}\n")
        for repo in missing_repos:
            print(f"  {RED}✗ {repo}{RESET}")
        print(f"\n{YELLOW}The script may not work correctly.{RESET}")
        response = input("\nContinue anyway? (y/n): ").lower()
        return response == 'y'
    
    return True


def get_time_greeting() -> str:
    """Generate greeting based on time of day."""
    current_hour = datetime.datetime.now().hour
    try:
        username = getpass.getuser().capitalize()
    except Exception:
        username = "User"

    if 0 <= current_hour < 12:
        greeting = "Good morning"
    elif 12 <= current_hour < 18:
        greeting = "Good afternoon"
    elif 18 <= current_hour < 22:
        greeting = "Good evening"
    else:
        greeting = "Good night"
    
    return f"{greeting} {username}"


def get_github_review_requests() -> int:
    """Get the number of pull requests requested for review on GitHub."""
    if shutil.which('gh') is None:
        return -1
    
    try:
        # Check for open PRs with review requested from the current user (@me)
        result = subprocess.run(
            ['gh', 'search', 'prs', '--review-requested=@me', '--state=open', '--json', 'number'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return -1
        
        prs = json.loads(result.stdout)
        return len(prs)
    except (json.JSONDecodeError, FileNotFoundError, Exception):
        return -1


def get_github_unread_notifications() -> int:
    """Get the number of unread notifications on GitHub."""
    if shutil.which('gh') is None:
        return -1
    
    try:
        result = subprocess.run(
            ['gh', 'api', 'notifications'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return -1
        
        notifications = json.loads(result.stdout)
        return len(notifications)
    except (json.JSONDecodeError, FileNotFoundError, Exception):
        return -1


def get_todays_calendar_events() -> List[str]:
    """Get today's calendar events using icalBuddy.

    Requires: brew install ical-buddy and the uuid of your calendar(s)
    Returns a list of output lines, or an empty list if unavailable / no events.
    """
    if shutil.which('icalBuddy') is None:
        return []

    try:
        result = subprocess.run(
            [
                'icalBuddy',
                '-b', '• ',        # bullet prefix for each event
                '-iep', 'title,datetime',  # show only title and time
                '-n',               # from now on 
                '-nc',              # no calendar names
                '-ic', # include following calendars. Comma separated. Get uuid using `icalBuddy calendars`
                ','.join(ICAL_CALENDAR_IDS),
                'eventsToday',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return []

        output = result.stdout.strip()
        if not output or 'No items.' in output:
            return []

        return [line for line in output.splitlines() if line.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return []


def show_menu():
    """Display the main menu."""
    global _startup_notice

    clear_screen()
    ascii_art = """                                           
                                ↑↑↑↑↑↑                
                                ↑↑↑↑↑↑                
                                ↑↑↑↑↑↑                
                                ↑↑↑↑↑↑                
                                ↑↑↑↑↑↑                
                                ↑↑↑↑↑↑                
                                ↑↑↑↑↑↑↑↑              
                     ↑↑↑         ↑↑↑↑↑↑↑↑↑            
                   ↑↑↑↑↑↑          ↑↑↑↑↑↑↑↑↑          
                 ↑↑↑↑↑↑↑↑↑↑          ↑↑↑↑↑↑↑↑↑        
               ↑↑↑↑↑↑↑↑↑↑↑↑↑↑          ↑↑↑↑↑↑↑↑↑      
              ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑          ↑↑↑↑↑↑↑↑↑    
            ↑↑↑↑↑↑↑↑    ↑↑↑↑↑↑↑↑↑          ↑↑↑↑↑↑↑↑   
          ↑↑↑↑↑↑↑↑↑       ↑↑↑↑↑↑↑↑↑         ↑↑↑↑↑↑↑↑↑ 
        ↑↑↑↑↑↑↑↑↑           ↑↑↑↑↑↑↑↑↑         ↑↑↑↑↑↑↑ 
       ↑↑↑↑↑↑↑↑              ↑↑↑↑↑↑↑↑          ↑↑↑↑↑↑ 
       ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
       ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
       ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
       ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
       ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
       ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
       ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
       ↑↑↑↑↑↑↑                 ↑↑↑↑↑↑          ↑↑↑↑↑↑ 
    """
    print(f"{ORANGE}{ascii_art}{RESET}")
    
    print("~" * 60)
    print(f"  {ORANGE}                        REPO-MAN{RESET}")
    print(f"                ✨Haya Repositories Manager✨")
    print("~" * 60)
    print("\nOptions:")
    notifications_label = "Hide notifications" if _show_notifications else "Show notifications"
    print("  1. Show git status of all repos")
    print("  2. Hard reset all to main")
    print("  3. Stash changes and checkout all to main")
    print("  4. Checkout specific branches")
    print("  5. Run make command")
    print("  6. Open a repo in code editor")
    print("  7. Show docker container info")
    print(f"  8. {notifications_label}")
    print("  9. Create new branches and checkout")
    print("  w. Worktrees")
    print("\n" + "~" * 60)
    print(f"\n{get_time_greeting()}")

    groups, _ = discover_worktree_groups()
    if len(groups) > 1:
        print(f"Active worktree group: {ORANGE}{_active_worktree_group}{RESET}")

    if _startup_notice:
        print(_startup_notice)
        _startup_notice = None

    if _show_notifications:
        # Trigger a background refresh if data is stale (non-blocking)
        refresh_cache_in_background()

        with _cache_lock:
            review_count       = _cache['review_count']
            notification_count = _cache['notification_count']
            calendar_events    = _cache['calendar_events']

        if review_count is not _LOADING and review_count >= 0:
            plural_s = "" if review_count == 1 else "s"
            print(f"You have {ORANGE}{review_count}{RESET} review{plural_s} requested on GitHub")

        if notification_count is not _LOADING and notification_count >= 0:
            plural_s = "" if notification_count == 1 else "s"
            print(f"You have {ORANGE}{notification_count}{RESET} unread notification{plural_s} on GitHub")

        if calendar_events and calendar_events is not _LOADING:
            print(f"\n{ORANGE}Today's calendar:{RESET}")
            for line in calendar_events:
                print(line)

    print("\n" + "~" * 60)


def option_1_show_status():
    """Option 1: Show git status of all repositories."""
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}GIT STATUS - ALL REPOSITORIES{RESET}")
    print("~" * 60)
    print()
    
    repo_paths = get_active_repo_paths()

    for repo_path in repo_paths:
        if not repo_path.exists():
            print(f"\n📁 {repo_path.name}")
            print(f"   {RED}✗ Repository not found{RESET}")
            continue
            
        print(f"\n📁 {repo_path.name}")
        print("-" * 60)
        
        # Get current branch
        returncode, branch, _ = run_git_command(
            repo_path, 
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            show_output=False
        )
        if returncode == 0:
            print(f"   Branch: {branch.strip()}")
        
        # Get short status
        returncode, status, stderr = run_git_command(
            repo_path,
            ['git', 'status', '--short'],
            show_output=False
        )
        
        if returncode != 0:
            print(f"   {RED}✗ Error getting status: {stderr}{RESET}")
        elif status.strip():
            print("   Changes:")
            for line in status.strip().split('\n'):
                print(f"     {line}")
        else:
            print(f"   {GREEN}✓ Clean working directory{RESET}")
    
    wait_for_key()


def option_2_reset_to_main():
    """
    Option 2: Reset all repos to main branch.

    """
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}RESET TO MAIN BRANCH{RESET}")
    print("~" * 60)
    print(f"\n{YELLOW}⚠️  WARNING: This is a DESTRUCTIVE operation!{RESET}\n")
    print("This will:")
    print("  • Discard ALL uncommitted changes (git reset --hard)")
    print("  • Checkout main branch")
    print("  • Pull latest changes from remote")
    print(f"\n{RED}All uncommitted work will be PERMANENTLY LOST!{RESET}")
    print()
    
    response = input("Are you sure you want to continue? (yes/no): ").lower()
    if response != 'yes':
        print(f"\n{RED}✗ Aborted.{RESET}")
        wait_for_key()
        return
    
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}RESETTING REPOSITORIES...{RESET}")
    print("~" * 60)
    
    repo_paths = get_active_repo_paths()

    for repo_path in repo_paths:
        if not repo_path.exists():
            print(f"\n{RED}✗ {repo_path.name}: Repository not found{RESET}")
            continue
            
        print(f"\n📁 {repo_path.name}")
        print("-" * 60)
        
        # Hard reset
        print("  • Resetting working directory...")
        returncode, _, stderr = run_git_command(repo_path, ['git', 'reset', '--hard'])
        if returncode != 0:
            print(f"    {RED}✗ Error: {stderr}{RESET}")
            continue
        else:
            print(f"    {GREEN}✓ Reset complete{RESET}")
        
        # Checkout main
        print("  • Checking out main branch...")
        returncode, _, stderr = run_git_command(repo_path, ['git', 'checkout', 'main'])
        if returncode != 0:
            print(f"    {RED}✗ Error: {stderr}{RESET}")
            continue
        else:
            print(f"    {GREEN}✓ On main branch{RESET}")
        
        # Pull latest
        print("  • Pulling latest changes...")
        returncode, stdout, stderr = run_git_command(repo_path, ['git', 'pull'])
        if returncode != 0:
            print(f"    {RED}✗ Error: {stderr}{RESET}")
        else:
            print(f"    {GREEN}✓ Pull complete{RESET}")
    
    print("~" * 60)
    print(f"{GREEN}✓ Reset complete for all repositories{RESET}")
    wait_for_key()


def option_3_stash_to_main():
    """
    Option 3: Stash changes and checkout main branch.
    
    """
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}STASH AND CHECKOUT MAIN{RESET}")
    print("~" * 60)
    print("\nThis will:")
    print("  • Stage all changes (git add .)")
    print("  • Stash changes with message 'wip'")
    print("  • Checkout main branch")
    print("  • Pull latest changes")
    print()
    
    print("Continue? (y/n): ", end='', flush=True)
    response = get_single_char().lower()
    print(response)
    if response != 'y':
        return
    
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}STASHING AND SWITCHING TO MAIN...{RESET}")
    print("~" * 60)
    
    repo_paths = get_active_repo_paths()

    for repo_path in repo_paths:
        if not repo_path.exists():
            print(f"\n{RED}✗ {repo_path.name}: Repository not found{RESET}")
            continue
            
        print(f"\n📁 {repo_path.name}")
        print("-" * 60)
        
        # Add all changes
        print("  • Staging all changes...")
        returncode, _, stderr = run_git_command(repo_path, ['git', 'add', '.'])
        if returncode != 0:
            print(f"    {RED}✗ Error: {stderr}{RESET}")
            continue
        else:
            print(f"    {GREEN}✓ Changes staged{RESET}")
        
        # Stash with message
        print("  • Stashing changes...")
        returncode, stdout, stderr = run_git_command(
            repo_path,
            ['git', 'stash', 'push', '-m', 'wip']
        )
        if returncode != 0:
            # Some errors are ok (e.g., "No local changes to save")
            if "No local changes to save" in stderr or "No local changes to save" in stdout:
                print("    ℹ  No changes to stash")
            else:
                print(f"    {RED}✗ Error: {stderr}{RESET}")
                continue
        else:
            print(f"    {GREEN}✓ Changes stashed{RESET}")
        
        # Checkout main
        print("  • Checking out main branch...")
        returncode, _, stderr = run_git_command(repo_path, ['git', 'checkout', 'main'])
        if returncode != 0:
            print(f"    {RED}✗ Error: {stderr}{RESET}")
            continue
        else:
            print(f"    {GREEN}✓ On main branch{RESET}")
        
        # Pull latest
        print("  • Pulling latest changes...")
        returncode, _, stderr = run_git_command(repo_path, ['git', 'pull'])
        if returncode != 0:
            print(f"    {RED}✗ Error: {stderr}{RESET}")
        else:
            print(f"    {GREEN}✓ Pull complete{RESET}")
    
    print("\n" + "~" * 60)
    print(f"{GREEN}✓ Stash and checkout complete for all repositories{RESET}")
    wait_for_key()


def option_4_checkout_branches():
    """
    Option 4: Checkout specific branches for each repository.

    """
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}CHECKOUT SPECIFIC BRANCHES{RESET}")
    print("~" * 60)
    print("\nFuzzy search fzf branch picker for each repository.")
    print("Press Esc to stay on the current branch and skip checkout.")
    print("Aborts if any repository has uncommitted changes.")
    print()

    if shutil.which('fzf') is None:
        print(f"{RED}✗ fzf is not installed or not in PATH.{RESET}")
        print(f"{YELLOW}Install fzf to use this option.{RESET}")
        wait_for_key()
        return
    
    # First, check all repos are clean
    all_clean = True
    dirty_repos = []
    
    repo_paths = get_active_repo_paths()

    for repo_path in repo_paths:
        if not repo_path.exists():
            continue
            
        returncode, status, _ = run_git_command(
            repo_path,
            ['git', 'status', '--short'],
            show_output=False
        )
        
        if returncode == 0 and status.strip():
            all_clean = False
            dirty_repos.append(repo_path.name)
    
    if not all_clean:
        print(f"{YELLOW}⚠️  The following repositories have uncommitted changes:{RESET}\n")
        for repo_name in dirty_repos:
            print(f"  {RED}✗ {repo_name}{RESET}")
        print(f"\n{YELLOW}Please commit, stash, or reset changes before using this option.{RESET}")
        print("(Use option 2 or 3 to handle uncommitted changes)")
        wait_for_key()
        return
    
    print(f"{GREEN}✓ All repositories are clean. Proceeding...{RESET}\n")
    
    for repo_path in repo_paths:
        if not repo_path.exists():
            print(f"\n{RED}✗ {repo_path.name}: Repository not found{RESET}")
            continue
        
        print(f"\n📁 {repo_path.name}")
        print("-" * 60)
        
        # Fetch latest
        print("  • Fetching from remote...")
        returncode, _, stderr = run_git_command(
            repo_path,
            ['git', 'fetch', '--all'],
            show_output=False
        )
        if returncode != 0:
            print(f"    {RED}✗ Error fetching: {stderr}{RESET}")
            continue
        else:
            print(f"    {GREEN}✓ Fetch complete{RESET}")
        
        # Show current branch
        returncode, current_branch, _ = run_git_command(
            repo_path,
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            show_output=False
        )
        if returncode == 0:
            print(f"    Current branch: {current_branch.strip()}")
        
        print("")
        try:
            selected, branch_name = pick_branch_with_fzf(repo_path)
        except RuntimeError as e:
            print(f"    {RED}✗ {e}{RESET}")
            continue

        if not selected:
            print("    ℹ  Skipped, staying on current branch")
            continue
        
        # Checkout branch
        print(f"  • Checking out '{branch_name}'...")
        returncode, stdout, stderr = run_git_command(
            repo_path,
            ['git', 'checkout', branch_name]
        )
        
        if returncode != 0:
            print(f"    {RED}✗ Error: {stderr}{RESET}")
        else:
            print(f"    {GREEN}✓ Successfully checked out '{branch_name}'{RESET}")
            # Pull latest changes on the newly checked-out branch
            print(f"  • Pulling latest changes...")
            returncode, _, stderr = run_git_command(
                repo_path,
                ['git', 'pull'],
                show_output=False
            )
            if returncode != 0:
                print(f"    {RED}✗ Error pulling: {stderr}{RESET}")
            else:
                print(f"    {GREEN}✓ Pulled latest changes{RESET}")
    
    print("\n" + "~" * 60)
    print(f"{GREEN}✓ Branch checkout complete{RESET}")
    wait_for_key()


def option_5_run_make_command():
    """
    Option 5: Run a make command in the parent repository.
    
    """
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}RUN MAKE COMMAND{RESET}")
    print("~" * 60)
    print()
    
    parent_repo = get_active_parent_repo_path()
    
    if not parent_repo.exists():
        print(f"{RED}✗ Parent repository not found: {parent_repo}{RESET}")
        wait_for_key()
        return
    
    makefile_path = parent_repo / 'Makefile'
    if not makefile_path.exists():
        print(f"{RED}✗ Makefile not found in: {parent_repo}{RESET}")
        wait_for_key()
        return
    
    print(f"Repository: {parent_repo}")
    print("\nSelect a command to run:")
    
    for cmd in MAKE_COMMANDS:
        print(f"  {cmd['key']}. {cmd['label']}")
    
    print("\nPress number to select command, or q to cancel.")
    
    choice = get_single_char()
    
    if choice in ('q', 'Q', '\x1b'):
        return

    selected_cmd = next((c for c in MAKE_COMMANDS if c['key'] == choice), None)
    
    if not selected_cmd:
        print(f"\n{RED}✗ Invalid selection.{RESET}")
        wait_for_key()
        return

    print(f"\nSelected: {ORANGE}{selected_cmd['label']}{RESET}")
    print(f"Command: {selected_cmd['command']}")
    
    response = input("\nRun this command? (y/n): ").lower()
    if response != 'y':
        print(f"\n{RED}✗ Aborted.{RESET}")
        wait_for_key()
        return
    
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}RUNNING: {selected_cmd['label']}...{RESET}")
    print("~" * 60)
    print()
    
    try:
        # Change to the parent repo directory
        original_dir = os.getcwd()
        os.chdir(parent_repo)
        
        returncode = os.system(selected_cmd['command'])
        
        os.chdir(original_dir)
        
        print("\n" + "~" * 60)
        if returncode == 0:
            print(f"{GREEN}✓ Command completed successfully{RESET}")
        else:
            print(f"{RED}✗ Command failed with exit code {returncode}{RESET}")
    
    except Exception as e:
        print(f"{RED}✗ Error running command: {e}{RESET}")
        # Make sure we restore the original directory
        try:
            os.chdir(original_dir)
        except:
            pass
    
    wait_for_key()


def option_6_open_in_code_editor():
    """
    Option 6: Open a repository in your code editor.
    
    """
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}OPEN REPO IN CODE EDITOR{RESET}")
    print("~" * 60)
    print("\nAvailable repositories:\n")
    

    
    repo_paths = get_active_repo_paths()

    # Display list of repos with numbers
    for i, repo_path in enumerate(repo_paths, 1):
        status = "✓" if repo_path.exists() else "✗"
        print(f"  {i}. {status} {ORANGE}{repo_path.name}{RESET}")
        print(f"      {repo_path}")
        print()
    
    print("\n" + "~" * 60)
    
    # Get user selection (single key, no Enter)
    try:
        print(f"\nSelect repository (1-{len(repo_paths)}, q, Esc): ", end='', flush=True)

        while True:
            choice = get_single_char()

            # q or Esc aborts back to main menu
            if choice in ('q', 'Q', '\x1b'):
                print()
                return

            print(choice)

            if choice.isdigit():
                repo_num = int(choice)
                if 1 <= repo_num <= len(repo_paths):
                    break

            print(f"{RED}✗ Invalid selection. Please choose 1-{len(repo_paths)}, q, or Esc.{RESET}")
            print(f"Select repository (1-{len(repo_paths)}, q, Esc): ", end='', flush=True)

        selected_repo = repo_paths[repo_num - 1]
        
        if not selected_repo.exists():
            print(f"\n{RED}✗ Repository does not exist: {selected_repo}{RESET}")
            wait_for_key()
            return
        
        selected_launcher, function_name = select_code_editor_launcher()
        if not selected_launcher:
            return

        print(f"\nOpening {selected_repo.name} in code editor...")
        returncode, message = open_repo_in_code_editor(selected_repo, function_name=function_name)
        
        if returncode == 0:
            print(f"{GREEN}✓ {message}{RESET}")
        else:
            print(f"\n{RED}✗ Failed to open code editor.{RESET}")
            if message:
                print(f"{RED}  {message}{RESET}")
        
        wait_for_key()

    except Exception as e:
        print(f"\n{RED}✗ Error: {e}{RESET}")
        wait_for_key()


def option_7_show_docker_info():
    """Option 7: Show a useful Docker container overview."""
    if shutil.which('docker') is None:
        clear_screen()
        print("~" * 60)
        print(f"  {ORANGE}DOCKER CONTAINER INFO{RESET}")
        print("~" * 60)
        print()
        print(f"{RED}✗ Docker CLI not found in PATH.{RESET}")
        print(f"{YELLOW}Install Docker Desktop or Docker CLI to use this option.{RESET}")
        wait_for_key()
        return

    action_feedback = ''

    while True:
        clear_screen()
        print("~" * 60)
        print(f"  {ORANGE}DOCKER CONTAINER INFO{RESET}")
        print("~" * 60)
        print()
        print("[p] prune stopped  [i] prune images  [n] prune networks  [v] prune volumes  [a] system prune  [q/esc] back")
        print()

        # Quick daemon check
        returncode, _, stderr = run_command(['docker', 'info'])
        if returncode != 0:
            print(f"{RED}✗ Docker is not available.{RESET}")
            print(f"{YELLOW}Make sure Docker Desktop/daemon is running.{RESET}")
            if stderr.strip():
                print(f"\n{RED}{stderr.strip()}{RESET}")
            print("\nPress q or Esc to return: ", end='', flush=True)
            choice = get_single_char()
            print()
            if choice in ('q', 'Q', '\x1b'):
                return
            continue

        # Summary counts
        rc_running, running_count, running_err = run_command([
            'docker', 'ps', '-q'
        ])
        rc_all, all_count, all_err = run_command([
            'docker', 'ps', '-aq'
        ])

        if rc_running == 0 and rc_all == 0:
            running_total = len([line for line in running_count.splitlines() if line.strip()])
            all_total = len([line for line in all_count.splitlines() if line.strip()])
            stopped_total = max(all_total - running_total, 0)
            print(f"Running: {GREEN}{running_total}{RESET}   Stopped: {YELLOW}{stopped_total}{RESET}   Total: {all_total}")
            print()
        elif running_err.strip() or all_err.strip():
            print(f"{YELLOW}⚠️  Could not compute container counts.{RESET}")
            print()

        # Container details (all containers)
        format_string = (
            '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t'
            '{{.Label "com.docker.compose.project"}}'
        )
        rc, output, err = run_command([
            'docker', 'ps', '-a', '--format', format_string
        ])

        if rc != 0:
            print(f"{RED}✗ Failed to list containers.{RESET}")
            if err.strip():
                print(f"{RED}{err.strip()}{RESET}")
        else:
            rows = [line for line in output.splitlines() if line.strip()]
            if not rows:
                print(f"{YELLOW}No containers found.{RESET}")
            else:
                headers = ["Name", "Image", "Status", "Ports", "Compose"]
                table_rows = []
                for row in rows:
                    parts = row.split('\t')
                    while len(parts) < 5:
                        parts.append('')
                    name, image, status, ports, compose_project = parts[:5]
                    ports = ports or '-'
                    compose_project = compose_project or '-'
                    table_rows.append([name, image, status, ports, compose_project])

                print_fixed_width_table(headers, table_rows)

        if action_feedback:
            print(f"\n{action_feedback}")
            action_feedback = ''

        print("\nAction: ", end='', flush=True)
        choice = get_single_char().lower()
        if choice in ('q', '\x1b'):
            print()
            return
        print(choice)

        if choice in ('p', 'i', 'n', 'v', 'a'):
            ok, message = run_docker_action(choice)
            if ok:
                action_feedback = f"{GREEN}✓ {message}{RESET}"
            else:
                action_feedback = f"{RED}✗ {message}{RESET}"
        else:
            action_feedback = f"{YELLOW}⚠️  Invalid action. Use p/i/n/v/a, q, or Esc.{RESET}"


def option_9_create_branches():
    """
    Option 9: Create new branches and checkout in all repositories.

    For each repo:
      - Skips if repo has uncommitted changes
      - fzf picker for source branch (current branch pre-selected)
      - Text input for new branch name (last created branch as default)
      - Checks out source branch, creates and checks out new branch
    """
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}CREATE NEW BRANCHES{RESET}")
    print("~" * 60)
    print("\nFor each repository:")
    print("  • Select source branch with fuzzy finder (current branch pre-selected)")
    print("  • Enter a name for the new branch")
    print("  • Create and checkout the new branch from the source branch")
    print("\nPress Esc at the branch picker to skip a repository.")
    print()

    if shutil.which('fzf') is None:
        print(f"{RED}✗ fzf is not installed or not in PATH.{RESET}")
        print(f"{YELLOW}Install fzf to use this option.{RESET}")
        wait_for_key()
        return

    # summary entries: {'repo': str, 'status': 'created'|'skipped'|'error', 'detail': str}
    summary: List[dict] = []
    last_branch_name: Optional[str] = None

    repo_paths = get_active_repo_paths()

    for repo_path in repo_paths:
        if not repo_path.exists():
            summary.append({'repo': repo_path.name, 'status': 'skipped', 'detail': 'Repository not found'})
            continue

        print(f"\n📁 {repo_path.name}")
        print("-" * 60)

        # Check repo is clean
        returncode, status_output, _ = run_git_command(
            repo_path,
            ['git', 'status', '--short'],
            show_output=False
        )
        if returncode == 0 and status_output.strip():
            print(f"  {YELLOW}⚠️  Skipping: repository has uncommitted changes{RESET}")
            summary.append({'repo': repo_path.name, 'status': 'skipped', 'detail': 'Uncommitted changes'})
            continue

        # Get current branch
        returncode, current_branch_raw, _ = run_git_command(
            repo_path,
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            show_output=False
        )
        current_branch = current_branch_raw.strip() if returncode == 0 else ''
        if current_branch:
            print(f"  Current branch: {ORANGE}{current_branch}{RESET}")

        # Pick source branch with fzf (current branch pre-selected)
        print("  Select source branch...")
        try:
            selected, source_branch = pick_source_branch_with_fzf(repo_path, current_branch)
        except RuntimeError as e:
            print(f"  {RED}✗ {e}{RESET}")
            summary.append({'repo': repo_path.name, 'status': 'error', 'detail': str(e)})
            continue

        if not selected:
            print(f"  {DIM}Skipped{RESET}")
            summary.append({'repo': repo_path.name, 'status': 'skipped', 'detail': 'Skipped, no changes'})
            continue

        print(f"  Selected source branch: {ORANGE}{source_branch}{RESET}")
        print()

        # Ask for new branch name, defaulting to the last branch created this session
        if last_branch_name:
            new_branch_name = _input_with_default(
                f"  New branch name [{last_branch_name}]: ",
                last_branch_name
            ).strip()
            if not new_branch_name:
                new_branch_name = last_branch_name
        else:
            new_branch_name = input("  New branch name: ").strip()

        if not new_branch_name:
            print(f"  {YELLOW}⚠️  Skipping: no branch name provided{RESET}")
            summary.append({'repo': repo_path.name, 'status': 'skipped', 'detail': 'No branch name provided'})
            continue

        # Checkout source branch first
        print(f"  • Checking out source branch '{source_branch}'...")
        returncode, _, stderr = run_git_command(
            repo_path,
            ['git', 'checkout', source_branch],
            show_output=False
        )
        if returncode != 0:
            err = stderr.strip()
            print(f"  {RED}✗ Failed to checkout source branch: {err}{RESET}")
            summary.append({'repo': repo_path.name, 'status': 'error', 'detail': f'Failed to checkout {source_branch}: {err}'})
            continue

        # Create and checkout new branch
        print(f"  • Creating and checking out '{new_branch_name}'...")
        returncode, _, stderr = run_git_command(
            repo_path,
            ['git', 'checkout', '-b', new_branch_name],
            show_output=False
        )
        if returncode != 0:
            err = stderr.strip()
            print(f"  {RED}✗ Failed to create branch: {err}{RESET}")
            summary.append({'repo': repo_path.name, 'status': 'error', 'detail': f'Failed to create {new_branch_name}: {err}'})
            continue

        print(f"  {GREEN}✓ Created and checked out '{new_branch_name}' from '{source_branch}'{RESET}")
        last_branch_name = new_branch_name
        summary.append({'repo': repo_path.name, 'status': 'created', 'detail': f'{source_branch} → {new_branch_name}'})

    # Summary
    print("\n" + "~" * 60)
    print(f"  {ORANGE}SUMMARY{RESET}")
    print("~" * 60)
    for entry in summary:
        if entry['status'] == 'created':
            print(f"  {GREEN}✓ {entry['repo']}{RESET}: {entry['detail']}")
        elif entry['status'] == 'error':
            print(f"  {RED}✗ {entry['repo']}{RESET}: {entry['detail']}")
        else:
            print(f"  {DIM}— {entry['repo']}{RESET}: {entry['detail']}")

    wait_for_key()


def show_worktrees_help() -> None:
    """Show a short help page for worktree group behavior in repo-man."""
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}WORKTREES HELP{RESET}")
    print("~" * 60)
    print()
    print("Git worktrees enable one repository to have multiple folders. But share git history.")
    print("You can have multiple branches of the same repo checked out at the same")
    print("time in different folders. So you can test a PR without affecting your work")
    print("in progress, or work on multiple features simultaneously, like hotfixes 😅")
    print()
    print("Great, but when you have nested repos like ours, switching worktrees")
    print("is not very convenient. But now we have repo-man™ to save the day!")
    print("Repo-man treats a 'worktree group' as a full set of all configured repos.")
    print("Each group has a name which corresponds to a folder at the root level.")   
    print("The original group is always 'main'.")
    print()
    print("Layout:")
    print(f"  {ROOT_PATH}/")
    print("    haysto-v2/                (main group parent repo)")
    print("    enquiry-form/")
    print("    <group-name>/")
    print("      haysto-v2/")
    print("      enquiry-form/")
    print()
    print("What Repo-man does:")
    print("  • Create group: ")
    print("    Creates a new worktree group in a folder with the name you give it.")
    print("    Then in the new worktrees, creates a new branch: `repo-man/<group>` from `main` branch")
    print("    for each repo (you can't have the same branch checked out in multiple worktrees,")
    print("    so we must create a new branch per repo for each group). Then sets upstream")
    print("    to origin/main and pulls with --ff-only. Oh and copies over your gitignored files.")
    print("    ⚠️ Avoid committing to the new branch and pushing! Create/checkout new branches.")
    print()
    print("  • Switch group: ")
    print("    Docker compose down on current, then up on new group. Sets the working directory of")
    print("    this app to use the new group's repos. ")
    print()
    print("  • Delete group: removes every worktree in that group and deletes the folder.")
    print()
    print("  • Cleanup group: removes stale/problematic worktrees for one group. ")
    print("    Useful if you manually delete a group's folder or if something gets messed up.")
    print()
    print("Safety:")
    print("  • You cannot create groups named 'main' or 'haysto-v2'")
    print("  • You cannot delete the main group")
    print("  • Cleanup cannot target 'main' or 'haysto-v2'")
    print("  • Group names allow letters, numbers, dash, underscore, dot")
    wait_for_key()


def option_worktrees_list_groups() -> None:
    """List valid and invalid worktree groups."""
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}WORKTREE GROUPS{RESET}")
    print("~" * 60)
    print()

    groups, invalid = discover_worktree_groups()
    for group in groups:
        marker = ''
        if group == MAIN_WORKTREE_GROUP:
            marker = ' (main)'
        if group == _active_worktree_group:
            marker = f"{marker} (active)"
        print(f"  {GREEN}✓ {group}{RESET}{marker}")

    if invalid:
        print(f"\n{YELLOW}Invalid candidates (not usable groups):{RESET}")
        for name, reason in sorted(invalid.items()):
            print(f"  {RED}✗ {name}{RESET}: {reason}")

    wait_for_key()


# Directories that are gitignored because they contain build artifacts, not config.
# We do not copy these when seeding a new worktree.
_ARTIFACT_DIR_PREFIXES = (
    'node_modules/',
    '.next/',
    '.nuxt/',
    '.output/',
    'dist/',
    'build/',
    'out/',
    '__pycache__/',
    '.mypy_cache/',
    '.pytest_cache/',
    '.ruff_cache/',
    '.venv/',
    'venv/',
    '.tox/',
    'coverage/',
    '.coverage',
    'htmlcoverage/',
    '.gradle/',
    '.idea/',
    '*.log',
)


def copy_gitignored_files(canonical_repo: Path, target_repo: Path) -> Tuple[int, List[str]]:
    """
    Copy gitignored files that exist in canonical_repo into the matching
    relative location inside target_repo.  Large artifact directories are
    excluded.  Returns (number_of_files_copied, list_of_error_strings).
    """
    result = subprocess.run(
        ['git', 'ls-files', '--others', '--ignored', '--exclude-standard', '-z'],
        cwd=canonical_repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0, [f'git ls-files failed: {result.stderr.strip()}']

    files = [f for f in result.stdout.split('\0') if f]
    copied = 0
    errors: List[str] = []

    for rel in files:
        # Skip large artifact paths
        if any(rel.startswith(prefix) or rel == prefix.rstrip('/') for prefix in _ARTIFACT_DIR_PREFIXES):
            continue
        src = canonical_repo / rel
        if not src.is_file():
            continue
        dst = target_repo / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
        except Exception as e:
            errors.append(f'{rel}: {e}')

    return copied, errors


def option_worktrees_create_group() -> None:
    """Create a new worktree group for all managed repositories."""
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}CREATE WORKTREE GROUP{RESET}")
    print("~" * 60)
    print()

    group_name = input("New worktree group name: ").strip()
    is_valid, reason = validate_worktree_group_name(group_name)
    if not is_valid:
        print(f"\n{RED}✗ Invalid group name: {reason}{RESET}")
        wait_for_key()
        return

    group_root = ROOT_PATH / group_name
    if group_root.exists():
        print(f"\n{RED}✗ Group folder already exists: {group_root}{RESET}")
        wait_for_key()
        return

    print(f"\nCreating worktree group {ORANGE}{group_name}{RESET}...")

    summary: List[Tuple[str, str, str]] = []
    all_ok = True
    worktree_branch = f"repo-man/{group_name}"

    for repo_rel in REPO_RELATIVE_PATHS:
        canonical_repo = (ROOT_PATH / repo_rel).resolve()
        target_repo = (group_root / repo_rel).resolve()

        if not canonical_repo.exists() or not (canonical_repo / '.git').exists():
            all_ok = False
            summary.append((str(repo_rel), 'error', 'Canonical repo missing or invalid'))
            continue

        if target_repo.exists():
            all_ok = False
            summary.append((str(repo_rel), 'error', 'Target path already exists'))
            continue

        target_repo.parent.mkdir(parents=True, exist_ok=True)

        # Prune stale worktree entries first so that a previously-deleted group
        # with the same name doesn't leave behind a "already used by worktree"
        # reference that would block the add.
        run_git_command(
            canonical_repo,
            ['git', 'worktree', 'prune', '--expire', 'now'],
            show_output=False
        )

        # We cannot check out 'main' in multiple worktrees at once.
        # Use a dedicated branch derived from main for this worktree group.
        returncode, _, stderr = run_git_command(
            canonical_repo,
            ['git', 'worktree', 'add', '-B', worktree_branch, str(target_repo), 'main'],
            show_output=False
        )
        if returncode != 0:
            all_ok = False
            summary.append((str(repo_rel), 'error', stderr.strip() or 'git worktree add failed'))
            continue

        upstream_code, _, upstream_err = run_git_command(
            target_repo,
            ['git', 'branch', '--set-upstream-to', 'origin/main', worktree_branch],
            show_output=False
        )
        if upstream_code != 0:
            all_ok = False
            summary.append((str(repo_rel), 'error', upstream_err.strip() or 'failed to set upstream'))
            continue

        pull_code, _, pull_err = run_git_command(target_repo, ['git', 'pull', '--ff-only'], show_output=False)
        if pull_code != 0:
            all_ok = False
            summary.append((str(repo_rel), 'error', pull_err.strip() or 'git pull failed'))
            continue

        copied_count, copy_errors = copy_gitignored_files(canonical_repo, target_repo)
        copy_note = f', copied {copied_count} gitignored file(s)'
        if copy_errors:
            copy_note += f' (with {len(copy_errors)} copy error(s): {" | ".join(copy_errors[:3])})'

        summary.append((str(repo_rel), 'ok', f"Created from main on '{worktree_branch}' and pulled latest{copy_note}"))

    print("\n" + "~" * 60)
    print(f"  {ORANGE}SUMMARY{RESET}")
    print("~" * 60)
    for repo_rel, status, message in summary:
        if status == 'ok':
            print(f"  {GREEN}✓ {repo_rel}{RESET}: {message}")
        else:
            print(f"  {RED}✗ {repo_rel}{RESET}: {message}")

    if all_ok:
        print(f"\n{GREEN}✓ Worktree group '{group_name}' created successfully{RESET}")
    else:
        print(f"\n{YELLOW}⚠️  Group creation finished with errors. Review summary above.{RESET}")

    wait_for_key()


def _select_worktree_group(prompt: str, include_main: bool = True) -> Tuple[bool, str]:
    """Select a worktree group using single-key input."""
    groups, _ = discover_worktree_groups()
    selectable = groups if include_main else [group for group in groups if group != MAIN_WORKTREE_GROUP]

    if not selectable:
        print(f"{YELLOW}No selectable worktree groups available.{RESET}")
        wait_for_key()
        return False, ''

    if len(selectable) > 9:
        print(f"{YELLOW}Too many groups for single-key menu. Keep 9 or fewer groups.{RESET}")
        wait_for_key()
        return False, ''

    print()
    for i, group in enumerate(selectable, 1):
        marker = ' (active)' if group == _active_worktree_group else ''
        print(f"  {i}. {group}{marker}")

    print("\nPress number to select, q or Esc to cancel")

    while True:
        print(f"\n{prompt} (1-{len(selectable)}, q, Esc): ", end='', flush=True)
        choice = get_single_char()
        print()

        if choice in ('q', 'Q', '\x1b'):
            return False, ''

        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(selectable):
                return True, selectable[index - 1]

        print(f"{RED}✗ Invalid choice.{RESET}")


def option_worktrees_switch_group() -> None:
    """Switch the active worktree group."""
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}SWITCH WORKTREE GROUP{RESET}")
    print("~" * 60)

    selected, target_group = _select_worktree_group('Select group', include_main=True)
    if not selected:
        return

    if target_group == _active_worktree_group:
        print(f"\n{YELLOW}⚠️  '{target_group}' is already active.{RESET}")
        wait_for_key()
        return

    is_valid, reason = validate_worktree_group(target_group)
    if not is_valid:
        print(f"\n{RED}✗ Cannot switch: {reason}{RESET}")
        wait_for_key()
        return

    warnings = set_active_worktree_group(target_group)
    print(f"\n{GREEN}✓ Active worktree group is now '{target_group}'{RESET}")
    if warnings:
        print(f"\n{YELLOW}Warnings:{RESET}")
        for warning in warnings:
            print(f"  {YELLOW}• {warning}{RESET}")

    wait_for_key()


def option_worktrees_delete_group() -> None:
    """Delete a non-main worktree group with confirmation."""
    global _active_worktree_group

    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}DELETE WORKTREE GROUP{RESET}")
    print("~" * 60)

    selected, group_name = _select_worktree_group('Delete group', include_main=False)
    if not selected:
        return

    if group_name == MAIN_WORKTREE_GROUP:
        print(f"\n{RED}✗ The main worktree group cannot be deleted.{RESET}")
        wait_for_key()
        return

    print(f"\n{RED}WARNING: This will remove all worktree folders in '{group_name}'.{RESET}")
    confirmation = input(f"Type '{group_name}' to confirm deletion: ").strip()
    if confirmation != group_name:
        print(f"\n{YELLOW}⚠️  Confirmation did not match. Aborted.{RESET}")
        wait_for_key()
        return

    is_active_group = group_name == _active_worktree_group
    if is_active_group:
        ok, message = run_docker_stack_down(get_active_parent_repo_path())
        if not ok:
            print(f"\n{YELLOW}⚠️  Docker down warning: {message}{RESET}")

    errors: List[str] = []
    group_root = ROOT_PATH / group_name
    for repo_rel in REPO_RELATIVE_PATHS:
        canonical_repo = (ROOT_PATH / repo_rel).resolve()
        target_repo = (group_root / repo_rel).resolve()

        if not target_repo.exists():
            continue

        returncode, _, stderr = run_git_command(
            canonical_repo,
            ['git', 'worktree', 'remove', str(target_repo)],
            show_output=False
        )
        if returncode != 0:
            err = stderr.strip() or 'git worktree remove failed'
            # If worktree has changes/locks, allow one force attempt.
            print(f"\n{YELLOW}⚠️  Could not remove {repo_rel}: {err}{RESET}")
            print("Try force remove this worktree? (y/n): ", end='', flush=True)
            force_choice = get_single_char().lower()
            print(force_choice)
            if force_choice == 'y':
                force_code, _, force_err = run_git_command(
                    canonical_repo,
                    ['git', 'worktree', 'remove', '--force', str(target_repo)],
                    show_output=False
                )
                if force_code != 0:
                    errors.append(f"{repo_rel}: {force_err.strip() or 'force remove failed'}")
            else:
                errors.append(f"{repo_rel}: removal skipped")

    if errors:
        print(f"\n{RED}✗ Group was not fully deleted:{RESET}")
        for err in errors:
            print(f"  {RED}• {err}{RESET}")
        wait_for_key()
        return

    if group_root.exists():
        try:
            shutil.rmtree(group_root)
        except Exception as e:
            print(f"\n{YELLOW}⚠️  Group worktrees removed, but folder cleanup failed: {e}{RESET}")

    if is_active_group:
        _active_worktree_group = MAIN_WORKTREE_GROUP
        save_active_worktree_group(_active_worktree_group)
        ok, message = run_docker_stack_up(get_active_parent_repo_path())
        if not ok:
            print(f"\n{YELLOW}⚠️  Docker up warning after reset to main: {message}{RESET}")

    print(f"\n{GREEN}✓ Deleted worktree group '{group_name}'{RESET}")
    wait_for_key()


def option_worktrees_cleanup_group() -> None:
    """Clean up problematic/orphaned worktrees for a non-main group."""
    clear_screen()
    print("~" * 60)
    print(f"  {ORANGE}CLEANUP WORKTREE GROUP{RESET}")
    print("~" * 60)
    print()
    print("Use this when a worktree group folder was deleted manually,")
    print("or when git still shows stale worktree entries for that group.")
    print()

    group_name = input("Group name to cleanup (not main): ").strip()
    if group_name in RESERVED_WORKTREE_GROUP_NAMES:
        print(f"\n{RED}✗ Cleanup is not allowed for '{group_name}'.{RESET}")
        wait_for_key()
        return

    is_valid, reason = validate_worktree_group_name(group_name)
    if not is_valid:
        print(f"\n{RED}✗ Invalid group name: {reason}{RESET}")
        wait_for_key()
        return

    if group_name == _active_worktree_group:
        print(f"\n{YELLOW}⚠️  '{group_name}' is currently active. Switch groups first.{RESET}")
        wait_for_key()
        return

    print(f"\n{YELLOW}This will only target worktrees under: {ROOT_PATH / group_name}{RESET}")
    confirmation = input(f"Type '{group_name}' to confirm cleanup: ").strip()
    if confirmation != group_name:
        print(f"\n{YELLOW}⚠️  Confirmation did not match. Aborted.{RESET}")
        wait_for_key()
        return

    group_root = (ROOT_PATH / group_name).resolve()
    group_branch = f"repo-man/{group_name}"
    summary: List[Tuple[str, str, str]] = []

    for repo_rel in REPO_RELATIVE_PATHS:
        canonical_repo = (ROOT_PATH / repo_rel).resolve()
        repo_label = str(repo_rel)

        if not canonical_repo.exists() or not (canonical_repo / '.git').exists():
            summary.append((repo_label, 'error', 'Canonical repo missing or invalid'))
            continue

        ok, worktree_paths, err = get_worktree_paths_for_repo(canonical_repo)
        if not ok:
            summary.append((repo_label, 'error', err or 'Failed to list worktrees'))
            continue

        removed_count = 0
        stale_matches = 0
        repaired_broken_folders = 0
        issues: List[str] = []

        for worktree_path in sorted(worktree_paths):
            try:
                worktree_path.relative_to(group_root)
            except ValueError:
                continue

            if not worktree_path.exists():
                stale_matches += 1
                continue

            # If the worktree folder exists but .git is missing, git worktree remove
            # fails validation. Remove the broken folder directly, then prune metadata.
            if not (worktree_path / '.git').exists():
                try:
                    shutil.rmtree(worktree_path)
                    repaired_broken_folders += 1
                    stale_matches += 1
                except Exception as e:
                    issues.append(f"Failed removing broken folder {worktree_path}: {e}")
                continue

            returncode, _, stderr = run_git_command(
                canonical_repo,
                ['git', 'worktree', 'remove', '--force', str(worktree_path)],
                show_output=False
            )
            if returncode == 0:
                removed_count += 1
            else:
                issues.append(stderr.strip() or f'Failed removing {worktree_path}')

        prune_code, prune_out, prune_err = run_command_in_dir(
            ['git', 'worktree', 'prune', '--expire', 'now', '--verbose'],
            canonical_repo
        )
        if prune_code != 0:
            issues.append((prune_err or prune_out or 'git worktree prune failed').strip())

        branch_code, _, branch_err = run_git_command(
            canonical_repo,
            ['git', 'branch', '-D', group_branch],
            show_output=False
        )
        if branch_code != 0:
            lowered = (branch_err or '').lower()
            if 'not found' not in lowered and 'not exist' not in lowered:
                issues.append(branch_err.strip() or f'Failed deleting branch {group_branch}')

        detail = (
            f"removed={removed_count}, repaired-broken={repaired_broken_folders}, "
            f"stale-matches={stale_matches}, pruned=yes"
        )
        if issues:
            summary.append((repo_label, 'error', f"{detail}; issues: {' | '.join(issues)}"))
        else:
            summary.append((repo_label, 'ok', detail))

    print("\n" + "~" * 60)
    print(f"  {ORANGE}CLEANUP SUMMARY{RESET}")
    print("~" * 60)
    had_errors = False
    for repo_label, status, detail in summary:
        if status == 'ok':
            print(f"  {GREEN}✓ {repo_label}{RESET}: {detail}")
        else:
            had_errors = True
            print(f"  {RED}✗ {repo_label}{RESET}: {detail}")

    # Remove the group root folder if it still exists — otherwise it remains
    # visible in 'list' as an invalid candidate.
    if not had_errors and group_root.exists():
        try:
            shutil.rmtree(group_root)
            print(f"\n{GREEN}✓ Removed group folder: {group_root}{RESET}")
        except Exception as e:
            print(f"\n{YELLOW}⚠️  Git metadata cleaned, but could not remove group folder: {e}{RESET}")

    if had_errors:
        print(f"\n{YELLOW}⚠️  Cleanup completed with some errors. See details above.{RESET}")
    else:
        print(f"\n{GREEN}✓ Cleanup complete for worktree group '{group_name}'.{RESET}")

    wait_for_key()


def option_w_worktrees() -> None:
    """Worktrees submenu."""
    while True:
        clear_screen()
        print("~" * 60)
        print(f"  {ORANGE}WORKTREES{RESET}")
        print("~" * 60)
        print()
        print("  1. List worktree groups")
        print("  2. Create a worktree group")
        print("  3. Switch worktree group")
        print("  4. Delete a worktree group")
        print("  5. Help")
        print("  6. Cleanup problematic worktrees")
        print("\nPress q or Esc to return")
        print("\n" + "~" * 60)

        print("\nSelect option (1-6, q, Esc): ", end='', flush=True)
        choice = get_single_char()
        print()

        if choice in ('q', 'Q', '\x1b'):
            return
        if choice == '1':
            option_worktrees_list_groups()
        elif choice == '2':
            option_worktrees_create_group()
        elif choice == '3':
            option_worktrees_switch_group()
        elif choice == '4':
            option_worktrees_delete_group()
        elif choice == '5':
            show_worktrees_help()
        elif choice == '6':
            option_worktrees_cleanup_group()
        else:
            print(f"\n{RED}✗ Invalid option. Please select 1-6.{RESET}")
            wait_for_key()


def main():
    """Main application loop."""
    # Validate repositories at startup
    clear_screen()
    print("Validating repositories...\n")
    if not validate_repos():
        print(f"\n{RED}✗ Exiting due to repository validation issues.{RESET}")
        sys.exit(1)

    initialise_active_worktree_group()
    
    # Main menu loop
    while True:
        show_menu()
        
        try:
            print("\nSelect option (1-9, w, q to quit): ", end='', flush=True)
            choice = get_single_char()
            print()  # New line after character is read

            global _show_notifications
            if choice == '1':
                option_1_show_status()
            elif choice == '2':
                option_2_reset_to_main()
            elif choice == '3':
                option_3_stash_to_main()
            elif choice == '4':
                option_4_checkout_branches()
            elif choice == '5':
                option_5_run_make_command()
            elif choice == '6':
                option_6_open_in_code_editor()
            elif choice == '7':
                option_7_show_docker_info()
            elif choice == '8':
                _show_notifications = not _show_notifications
                if _show_notifications:
                    # Block until data is loaded so the menu renders with values immediately
                    _run_cache_fetch()
            elif choice == '9':
                option_9_create_branches()
            elif choice in ('w', 'W'):
                option_w_worktrees()
            elif choice == 'q' or choice == 'Q' or choice == '\x1b':
                clear_screen()
                print("Goodbye! 👋")
                sys.exit(0)
            else:
                print(f"\n{RED}✗ Invalid option. Please select 1-9 or w.{RESET}")
                wait_for_key()
        
        except KeyboardInterrupt:
            clear_screen()
            print("\n\nInterrupted by user. Goodbye! 👋")
            sys.exit(0)
        except Exception as e:
            print(f"\n{RED}✗ Unexpected error: {e}{RESET}")
            wait_for_key()


if __name__ == "__main__":
    main()
