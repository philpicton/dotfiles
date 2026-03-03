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
from typing import List, Optional, Tuple


# Repository paths 
# Put haya parent repo first
# Then sub repos and any other you wish to manage below.
# Customise the paths to your local setup 
REPOS = [
    "~/code/haysto-v2",
    "~/code/haysto-v2/haysto-v2-api",
    "~/code/haysto-v2/haysto-v2-collect",
    "~/code/haysto-v2/haysto-v2-create",
    "~/code/haysto-v2/lib/js/haysto-v2-lib_shared",
    "~/code/enquiry-form",
]

# Expand paths and convert to absolute paths
REPO_PATHS = [Path(repo).expanduser().resolve() for repo in REPOS]

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

    for option in EDITOR_MENU_OPTIONS:
        print(f"  {option['key']}. {option['label']}")

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
                '3E7B91E3-B0EE-4A63-8856-3FED7A55F71D',
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
    print("  9. Quit")
    print("\n" + "~" * 60)
    print(f"\n{get_time_greeting()}")

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
    
    for repo_path in REPO_PATHS:
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
    
    for repo_path in REPO_PATHS:
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
    
    for repo_path in REPO_PATHS:
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
    
    for repo_path in REPO_PATHS:
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
    
    for repo_path in REPO_PATHS:
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
    
    parent_repo = REPO_PATHS[0]  # ~/code/haysto-v2
    
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
    

    
    # Display list of repos with numbers
    for i, repo_path in enumerate(REPO_PATHS, 1):
        status = "✓" if repo_path.exists() else "✗"
        print(f"  {i}. {status} {repo_path.name}")
        print(f"      {repo_path}")
    
    print("\n" + "~" * 60)
    
    # Get user selection (single key, no Enter)
    try:
        print(f"\nSelect repository (1-{len(REPO_PATHS)}, q, Esc): ", end='', flush=True)

        while True:
            choice = get_single_char()

            # q or Esc aborts back to main menu
            if choice in ('q', 'Q', '\x1b'):
                print()
                return

            print(choice)

            if choice.isdigit():
                repo_num = int(choice)
                if 1 <= repo_num <= len(REPO_PATHS):
                    break

            print(f"{RED}✗ Invalid selection. Please choose 1-{len(REPO_PATHS)}, q, or Esc.{RESET}")
            print(f"Select repository (1-{len(REPO_PATHS)}, q, Esc): ", end='', flush=True)

        selected_repo = REPO_PATHS[repo_num - 1]
        
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


def main():
    """Main application loop."""
    # Validate repositories at startup
    clear_screen()
    print("Validating repositories...\n")
    if not validate_repos():
        print(f"\n{RED}✗ Exiting due to repository validation issues.{RESET}")
        sys.exit(1)
    
    # Main menu loop
    while True:
        show_menu()
        
        try:
            print("\nSelect option (1-9 or q to quit): ", end='', flush=True)
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
            elif choice == '9' or choice == 'q' or choice == 'Q' or choice == '\x1b':
                clear_screen()
                print("Goodbye! 👋")
                sys.exit(0)
            else:
                print(f"\n{RED}✗ Invalid option. Please select 1-9.{RESET}")
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
