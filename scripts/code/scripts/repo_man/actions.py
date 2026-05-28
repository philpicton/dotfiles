"""Main menu actions and application entry flow for repo-man."""

import os
import subprocess
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from . import dashboard, worktrees
from .context import AppConfig, AppState
from .shell import (
    input_with_default,
    open_repo_in_kitty_tab,
    open_repos_in_kitty_tabs,
    pick_branch_with_fzf,
    pick_source_branch_with_fzf,
    run_command,
    run_git_command,
)
from .ui import (
    DIM,
    GREEN,
    ORANGE,
    RED,
    RESET,
    YELLOW,
    clear_screen,
    get_single_char,
    get_time_greeting,
    print_fixed_width_table,
    wait_for_key,
)


KITTY_BATCH_REPO_NAMES = (
    "haysto-v2-api",
    "haysto-v2-collect",
    "haysto-v2-create",
    "haysto-v2-lib_shared",
)


def make_command_changes_docker_stack(command: str) -> bool:
    """Return True when a configured make command is expected to restart the stack."""
    stripped = command.strip()
    docker_make_prefixes = (
        "make init",
        "make restart",
        "make up",
    )
    return any(stripped.startswith(prefix) for prefix in docker_make_prefixes)


def get_worktree_database_bootstrap_command() -> Dict[str, str]:
    """Return the built-in command used to initialise a non-main worktree DB."""
    return {
        "key": "9",
        "label": "Initialise current worktree database",
        "command": (
            "docker compose exec haysto-api php artisan migrate --seed"
            " && docker compose exec haysto-api php artisan db:reseed-permissions"
        ),
    }


def choose_extra_command_key(existing_commands: List[Dict[str, str]]) -> str:
    """Pick a free single-key slot for a built-in dynamic menu command."""
    used_keys = {command["key"] for command in existing_commands}
    for candidate in ["9", "a", "b", "c", "d", "e", "f"]:
        if candidate not in used_keys:
            return candidate
    return "z"


def get_make_commands_for_current_group(config: AppConfig, state: AppState) -> List[Dict[str, str]]:
    """Return the option 5 command list for the active worktree group."""
    commands = [dict(command) for command in config.make_commands]
    if state.active_worktree_group == config.main_worktree_group:
        return commands

    filtered_commands = [
        command for command in commands
        if command["command"].strip() != "make init"
    ]
    bootstrap_command = get_worktree_database_bootstrap_command()
    bootstrap_command["key"] = choose_extra_command_key(filtered_commands)
    filtered_commands.append(bootstrap_command)
    return filtered_commands


def get_kitty_batch_repo_paths(repo_paths: List[Path]) -> Tuple[List[Path], List[str]]:
    """Return the configured multi-open repo paths in their required order."""
    repo_paths_by_name = {repo_path.name: repo_path for repo_path in repo_paths}
    resolved_repo_paths = []
    missing_repo_names = []

    for repo_name in KITTY_BATCH_REPO_NAMES:
        repo_path = repo_paths_by_name.get(repo_name)
        if repo_path is None:
            missing_repo_names.append(repo_name)
            continue
        resolved_repo_paths.append(repo_path)

    return resolved_repo_paths, missing_repo_names


def validate_repos(config: AppConfig) -> bool:
    """Check that the configured repositories exist and look like git repos."""
    all_exist = True
    missing_repos = []

    for repo_path in config.repo_paths:
        if not repo_path.exists():
            all_exist = False
            missing_repos.append(str(repo_path))
        elif not (repo_path / ".git").exists():
            all_exist = False
            missing_repos.append("{repo} (not a git repository)".format(repo=repo_path))

    if not all_exist:
        print("{yellow}⚠️  WARNING: Some repositories are missing or invalid:{reset}\n".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        for repo in missing_repos:
            print("  {red}✗ {repo}{reset}".format(red=RED, repo=repo, reset=RESET))
        print("\n{yellow}The script may not work correctly.{reset}".format(yellow=YELLOW, reset=RESET))
        response = input("\nContinue anyway? (y/n): ").lower()
        return response == "y"

    return True


def show_menu(config: AppConfig, state: AppState) -> None:
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
    print("{orange}{art}{reset}".format(orange=ORANGE, art=ascii_art, reset=RESET))

    print("~" * 60)
    print("  {orange}                        REPO-MAN{reset}".format(orange=ORANGE, reset=RESET))
    print("                ✨Haya Repositories Manager✨")
    print("~" * 60)
    print("\nOptions:")
    notifications_label = "Hide notifications" if state.show_notifications else "Show notifications"
    print("  1. Show git status of all repos")
    print("  2. Hard reset all to main")
    print("  3. Stash changes and checkout all to main")
    print("  4. Checkout specific branches")
    print("  5. Run make command")
    print("  6. Open repo in Kitty / nvim")
    print("  7. Show docker container info")
    print("  8. {label}".format(label=notifications_label))
    print("  9. Create new branches and checkout")
    print("  w. Worktrees")
    print("\n" + "~" * 60)
    print("\n{greeting}".format(greeting=get_time_greeting()))

    groups, _ = worktrees.discover_worktree_groups(config)
    if len(groups) > 1:
        print("Active worktree group: {orange}{group}{reset}".format(
            orange=ORANGE,
            group=state.active_worktree_group,
            reset=RESET,
        ))

    docker_running_groups = worktrees.get_groups_with_running_docker_stacks(config, groups)
    if docker_running_groups:
        if len(docker_running_groups) == 1:
            print("Docker active worktree: {orange}{group}{reset}".format(
                orange=ORANGE,
                group=docker_running_groups[0],
                reset=RESET,
            ))
        else:
            print("Docker active worktrees: {orange}{groups}{reset}".format(
                orange=ORANGE,
                groups=", ".join(docker_running_groups),
                reset=RESET,
            ))

    if state.startup_notice:
        print(state.startup_notice)
        state.startup_notice = None

    if state.show_notifications:
        dashboard.refresh_cache_in_background(config, state)
        review_count, notification_count, calendar_events = dashboard.get_cache_snapshot(state)

        if review_count is not state.loading_sentinel and review_count >= 0:
            plural_s = "" if review_count == 1 else "s"
            print("You have {orange}{count}{reset} review{plural} requested on GitHub".format(
                orange=ORANGE,
                count=review_count,
                reset=RESET,
                plural=plural_s,
            ))

        if notification_count is not state.loading_sentinel and notification_count >= 0:
            plural_s = "" if notification_count == 1 else "s"
            print("You have {orange}{count}{reset} unread notification{plural} on GitHub".format(
                orange=ORANGE,
                count=notification_count,
                reset=RESET,
                plural=plural_s,
            ))

        if calendar_events and calendar_events is not state.loading_sentinel:
            print("\n{orange}Today's calendar:{reset}".format(orange=ORANGE, reset=RESET))
            for line in calendar_events:
                print(line)

    print("\n" + "~" * 60)


def option_1_show_status(config: AppConfig, state: AppState) -> None:
    """Option 1: Show git status of all repositories."""
    clear_screen()
    print("~" * 60)
    print("  {orange}GIT STATUS - ALL REPOSITORIES{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print()

    repo_paths = config.repo_paths_for_group(state.active_worktree_group)

    for repo_path in repo_paths:
        if not repo_path.exists():
            print("\n📁 {name}".format(name=repo_path.name))
            print("   {red}✗ Repository not found{reset}".format(red=RED, reset=RESET))
            continue

        print("\n📁 {name}".format(name=repo_path.name))
        print("-" * 60)

        returncode, branch, _ = run_git_command(
            repo_path,
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            show_output=False,
        )
        if returncode == 0:
            print("   Branch: {branch}".format(branch=branch.strip()))

        returncode, status, stderr = run_git_command(
            repo_path,
            ["git", "status", "--short"],
            show_output=False,
        )

        if returncode != 0:
            print("   {red}✗ Error getting status: {stderr}{reset}".format(
                red=RED,
                stderr=stderr,
                reset=RESET,
            ))
        elif status.strip():
            print("   Changes:")
            for line in status.strip().split("\n"):
                print("     {line}".format(line=line))
        else:
            print("   {green}✓ Clean working directory{reset}".format(green=GREEN, reset=RESET))

    wait_for_key()


def option_2_reset_to_main(config: AppConfig, state: AppState) -> None:
    """Option 2: Reset all repos to the main branch."""
    clear_screen()
    print("~" * 60)
    print("  {orange}RESET TO MAIN BRANCH{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print("\n{yellow}⚠️  WARNING: This is a DESTRUCTIVE operation!{reset}\n".format(
        yellow=YELLOW,
        reset=RESET,
    ))
    print("This will:")
    print("  • Discard ALL uncommitted changes (git reset --hard)")
    print("  • Checkout main branch")
    print("  • Pull latest changes from remote")
    print("\n{red}All uncommitted work will be PERMANENTLY LOST!{reset}".format(red=RED, reset=RESET))
    print()

    response = input("Are you sure you want to continue? (yes/no): ").lower()
    if response != "yes":
        print("\n{red}✗ Aborted.{reset}".format(red=RED, reset=RESET))
        wait_for_key()
        return

    clear_screen()
    print("~" * 60)
    print("  {orange}RESETTING REPOSITORIES...{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)

    repo_paths = config.repo_paths_for_group(state.active_worktree_group)

    for repo_path in repo_paths:
        if not repo_path.exists():
            print("\n{red}✗ {repo}: Repository not found{reset}".format(
                red=RED,
                repo=repo_path.name,
                reset=RESET,
            ))
            continue

        print("\n📁 {repo}".format(repo=repo_path.name))
        print("-" * 60)

        print("  • Resetting working directory...")
        returncode, _, stderr = run_git_command(repo_path, ["git", "reset", "--hard"])
        if returncode != 0:
            print("    {red}✗ Error: {stderr}{reset}".format(red=RED, stderr=stderr, reset=RESET))
            continue
        print("    {green}✓ Reset complete{reset}".format(green=GREEN, reset=RESET))

        print("  • Checking out main branch...")
        returncode, _, stderr = run_git_command(repo_path, ["git", "checkout", "main"])
        if returncode != 0:
            print("    {red}✗ Error: {stderr}{reset}".format(red=RED, stderr=stderr, reset=RESET))
            continue
        print("    {green}✓ On main branch{reset}".format(green=GREEN, reset=RESET))

        print("  • Pulling latest changes...")
        returncode, _, stderr = run_git_command(repo_path, ["git", "pull", "--ff-only"])
        if returncode != 0:
            print("    {red}✗ Error: {stderr}{reset}".format(red=RED, stderr=stderr, reset=RESET))
        else:
            print("    {green}✓ Pull complete{reset}".format(green=GREEN, reset=RESET))

    print("~" * 60)
    print("{green}✓ Reset complete for all repositories{reset}".format(green=GREEN, reset=RESET))
    wait_for_key()


def option_3_stash_to_main(config: AppConfig, state: AppState) -> None:
    """Option 3: Stash changes and then switch every repo back to main."""
    clear_screen()
    print("~" * 60)
    print("  {orange}STASH AND CHECKOUT MAIN{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print("\nThis will:")
    print("  • Stage all changes (git add .)")
    print("  • Stash changes with message 'wip'")
    print("  • Checkout main branch")
    print("  • Pull latest changes")
    print()

    print("Continue? (y/n): ", end="", flush=True)
    response = get_single_char().lower()
    print(response)
    if response != "y":
        return

    clear_screen()
    print("~" * 60)
    print("  {orange}STASHING AND SWITCHING TO MAIN...{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)

    repo_paths = config.repo_paths_for_group(state.active_worktree_group)

    for repo_path in repo_paths:
        if not repo_path.exists():
            print("\n{red}✗ {repo}: Repository not found{reset}".format(
                red=RED,
                repo=repo_path.name,
                reset=RESET,
            ))
            continue

        print("\n📁 {repo}".format(repo=repo_path.name))
        print("-" * 60)

        print("  • Staging all changes...")
        returncode, _, stderr = run_git_command(repo_path, ["git", "add", "."])
        if returncode != 0:
            print("    {red}✗ Error: {stderr}{reset}".format(red=RED, stderr=stderr, reset=RESET))
            continue
        print("    {green}✓ Changes staged{reset}".format(green=GREEN, reset=RESET))

        print("  • Stashing changes...")
        returncode, stdout, stderr = run_git_command(
            repo_path,
            ["git", "stash", "push", "-m", "wip"],
        )
        if returncode != 0:
            if "No local changes to save" in stderr or "No local changes to save" in stdout:
                print("    ℹ  No changes to stash")
            else:
                print("    {red}✗ Error: {stderr}{reset}".format(red=RED, stderr=stderr, reset=RESET))
                continue
        else:
            print("    {green}✓ Changes stashed{reset}".format(green=GREEN, reset=RESET))

        print("  • Checking out main branch...")
        returncode, _, stderr = run_git_command(repo_path, ["git", "checkout", "main"])
        if returncode != 0:
            print("    {red}✗ Error: {stderr}{reset}".format(red=RED, stderr=stderr, reset=RESET))
            continue
        print("    {green}✓ On main branch{reset}".format(green=GREEN, reset=RESET))

        print("  • Pulling latest changes...")
        returncode, _, stderr = run_git_command(repo_path, ["git", "pull", "--ff-only"])
        if returncode != 0:
            print("    {red}✗ Error: {stderr}{reset}".format(red=RED, stderr=stderr, reset=RESET))
        else:
            print("    {green}✓ Pull complete{reset}".format(green=GREEN, reset=RESET))

    print("\n" + "~" * 60)
    print("{green}✓ Stash and checkout complete for all repositories{reset}".format(green=GREEN, reset=RESET))
    wait_for_key()


def option_4_checkout_branches(config: AppConfig, state: AppState) -> None:
    """Option 4: Checkout specific branches for each repository."""
    clear_screen()
    print("~" * 60)
    print("  {orange}CHECKOUT SPECIFIC BRANCHES{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print("\nFuzzy search fzf branch picker for each repository.")
    print("Press Esc to stay on the current branch and skip checkout.")
    print("Aborts if any repository has uncommitted changes.")
    print()

    if shutil.which("fzf") is None:
        print("{red}✗ fzf is not installed or not in PATH.{reset}".format(red=RED, reset=RESET))
        print("{yellow}Install fzf to use this option.{reset}".format(yellow=YELLOW, reset=RESET))
        wait_for_key()
        return

    all_clean = True
    dirty_repos = []
    repo_paths = config.repo_paths_for_group(state.active_worktree_group)

    for repo_path in repo_paths:
        if not repo_path.exists():
            continue

        returncode, status, _ = run_git_command(
            repo_path,
            ["git", "status", "--short"],
            show_output=False,
        )

        if returncode == 0 and status.strip():
            all_clean = False
            dirty_repos.append(repo_path.name)

    if not all_clean:
        print("{yellow}⚠️  The following repositories have uncommitted changes:{reset}\n".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        for repo_name in dirty_repos:
            print("  {red}✗ {repo}{reset}".format(red=RED, repo=repo_name, reset=RESET))
        print("\n{yellow}Please commit, stash, or reset changes before using this option.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        print("(Use option 2 or 3 to handle uncommitted changes)")
        wait_for_key()
        return

    print("{green}✓ All repositories are clean. Proceeding...{reset}\n".format(green=GREEN, reset=RESET))

    for repo_path in repo_paths:
        if not repo_path.exists():
            print("\n{red}✗ {repo}: Repository not found{reset}".format(
                red=RED,
                repo=repo_path.name,
                reset=RESET,
            ))
            continue

        print("\n📁 {repo}".format(repo=repo_path.name))
        print("-" * 60)

        print("  • Fetching from remote...")
        returncode, _, stderr = run_git_command(
            repo_path,
            ["git", "fetch", "--all"],
            show_output=False,
        )
        if returncode != 0:
            print("    {red}✗ Error fetching: {stderr}{reset}".format(
                red=RED,
                stderr=stderr,
                reset=RESET,
            ))
            continue
        print("    {green}✓ Fetch complete{reset}".format(green=GREEN, reset=RESET))

        returncode, current_branch, _ = run_git_command(
            repo_path,
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            show_output=False,
        )
        if returncode == 0:
            print("    Current branch: {branch}".format(branch=current_branch.strip()))

        print("")
        try:
            selected, branch_name = pick_branch_with_fzf(repo_path)
        except RuntimeError as exc:
            print("    {red}✗ {error}{reset}".format(red=RED, error=exc, reset=RESET))
            continue

        if not selected:
            print("    ℹ  Skipped, staying on current branch")
            continue

        print("  • Checking out '{branch}'...".format(branch=branch_name))
        returncode, _, stderr = run_git_command(
            repo_path,
            ["git", "checkout", branch_name],
        )

        if returncode != 0:
            print("    {red}✗ Error: {stderr}{reset}".format(red=RED, stderr=stderr, reset=RESET))
        else:
            print("    {green}✓ Successfully checked out '{branch}'{reset}".format(
                green=GREEN,
                branch=branch_name,
                reset=RESET,
            ))
            print("  • Pulling latest changes...")
            returncode, _, stderr = run_git_command(
                repo_path,
                ["git", "pull", "--ff-only"],
                show_output=False,
            )
            if returncode != 0:
                print("    {red}✗ Error pulling: {stderr}{reset}".format(
                    red=RED,
                    stderr=stderr,
                    reset=RESET,
                ))
            else:
                print("    {green}✓ Pulled latest changes{reset}".format(green=GREEN, reset=RESET))

    print("\n" + "~" * 60)
    print("{green}✓ Branch checkout complete{reset}".format(green=GREEN, reset=RESET))
    wait_for_key()


def option_5_run_make_command(config: AppConfig, state: AppState) -> None:
    """Option 5: Run one configured make command in the parent repository."""
    clear_screen()
    print("~" * 60)
    print("  {orange}RUN MAKE COMMAND{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print()

    parent_repo = config.parent_repo_path_for_group(state.active_worktree_group)

    if not parent_repo.exists():
        print("{red}✗ Parent repository not found: {repo}{reset}".format(
            red=RED,
            repo=parent_repo,
            reset=RESET,
        ))
        wait_for_key()
        return

    makefile_path = parent_repo / "Makefile"
    if not makefile_path.exists():
        print("{red}✗ Makefile not found in: {repo}{reset}".format(
            red=RED,
            repo=parent_repo,
            reset=RESET,
        ))
        wait_for_key()
        return

    available_commands = get_make_commands_for_current_group(config, state)

    print("Repository: {repo}".format(repo=parent_repo))
    print("\nSelect a command to run:")

    if state.active_worktree_group != config.main_worktree_group:
        print("{yellow}Non-main worktree detected: make init is hidden here because it is not worktree-safe.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        print("Use the worktrees menu to initialise the active worktree stack instead.\n")

    for cmd in available_commands:
        print("  {key}. {label}".format(key=cmd["key"], label=cmd["label"]))

    print("\nPress a command key to select, or q to cancel.")

    choice = get_single_char()
    if choice in ("q", "Q", "\x1b"):
        return

    selected_cmd = next((command for command in available_commands if command["key"] == choice), None)
    if not selected_cmd:
        print("\n{red}✗ Invalid selection.{reset}".format(red=RED, reset=RESET))
        wait_for_key()
        return

    print("\nSelected: {orange}{label}{reset}".format(
        orange=ORANGE,
        label=selected_cmd["label"],
        reset=RESET,
    ))
    print("Command: {command}".format(command=selected_cmd["command"]))

    response = input("\nRun this command? (y/n): ").lower()
    if response != "y":
        print("\n{red}✗ Aborted.{reset}".format(red=RED, reset=RESET))
        wait_for_key()
        return

    clear_screen()
    print("~" * 60)
    print("  {orange}RUNNING: {label}...{reset}".format(
        orange=ORANGE,
        label=selected_cmd["label"],
        reset=RESET,
    ))
    print("~" * 60)
    print()

    original_dir = os.getcwd()
    try:
        if make_command_changes_docker_stack(selected_cmd["command"]):
            stopped_groups, warnings = worktrees.stop_other_running_docker_stacks(
                config,
                state.active_worktree_group,
            )
            for group in stopped_groups:
                print("Stopped docker stack for group: {group}".format(group=group))
            for warning in warnings:
                print("{yellow}⚠️  {warning}{reset}".format(
                    yellow=YELLOW,
                    warning=warning,
                    reset=RESET,
                ))

        compose_env = worktrees.build_compose_environment(config, state.active_worktree_group, parent_repo)
        os.chdir(parent_repo)
        result = subprocess.run(
            selected_cmd["command"],
            cwd=parent_repo,
            shell=True,
            env=compose_env,
        )
        returncode = result.returncode

        dependency_warning = ""
        if (
            returncode == 0
            and make_command_changes_docker_stack(selected_cmd["command"])
            and state.active_worktree_group != config.main_worktree_group
        ):
            deps_ok, deps_message = worktrees.refresh_worktree_api_dependencies(
                config,
                state.active_worktree_group,
                parent_repo,
            )
            if not deps_ok:
                dependency_warning = deps_message

        os.chdir(original_dir)

        print("\n" + "~" * 60)
        if returncode == 0 and not dependency_warning:
            print("{green}✓ Command completed successfully{reset}".format(green=GREEN, reset=RESET))
        elif returncode == 0:
            print("{yellow}⚠️  Command completed, but API dependency refresh failed: {message}{reset}".format(
                yellow=YELLOW,
                message=dependency_warning,
                reset=RESET,
            ))
        else:
            print("{red}✗ Command failed with exit code {code}{reset}".format(
                red=RED,
                code=returncode,
                reset=RESET,
            ))
    except Exception as exc:
        print("{red}✗ Error running command: {error}{reset}".format(red=RED, error=exc, reset=RESET))
        try:
            os.chdir(original_dir)
        except Exception:
            pass

    wait_for_key()


def option_6_open_in_code_editor(config: AppConfig, state: AppState) -> None:
    """Option 6: Open one or more repositories in Kitty/nvim."""
    clear_screen()
    print("~" * 60)
    print("  {orange}OPEN REPO IN KITTY / NVIM{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print("\nAvailable repositories:\n")

    repo_paths = config.repo_paths_for_group(state.active_worktree_group)
    batch_repo_paths, missing_batch_repo_names = get_kitty_batch_repo_paths(repo_paths)

    if len(repo_paths) > 9:
        print("{yellow}Too many repositories for single-key selection. Keep 9 or fewer repos.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        wait_for_key()
        return

    for i, repo_path in enumerate(repo_paths, 1):
        status = "✓" if repo_path.exists() else "✗"
        print("  {index}. {status} {orange}{name}{reset}".format(
            index=i,
            status=status,
            orange=ORANGE,
            name=repo_path.name,
            reset=RESET,
        ))
        print("      {path}".format(path=repo_path))
        print()

    batch_status = "✓" if not missing_batch_repo_names and all(
        repo_path.exists() for repo_path in batch_repo_paths
    ) else "✗"
    print("  a. {status} {orange}Open api, collect, create, and shared lib in Kitty tabs{reset}".format(
        status=batch_status,
        orange=ORANGE,
        reset=RESET,
    ))
    print("      haysto-v2-api -> haysto-v2-collect -> haysto-v2-create -> haysto-v2-lib_shared")
    print()

    print("\n" + "~" * 60)

    try:
        prompt = "Select repository (1-{count}, a, q, Esc): ".format(count=len(repo_paths))
        print("\n{prompt}".format(prompt=prompt), end="", flush=True)

        while True:
            choice = get_single_char()

            if choice in ("q", "Q", "\x1b"):
                print()
                return

            print(choice)

            if choice == "a":
                if missing_batch_repo_names:
                    print("{red}✗ Batch open is missing configured repos: {names}{reset}".format(
                        red=RED,
                        names=", ".join(missing_batch_repo_names),
                        reset=RESET,
                    ))
                    print(prompt, end="", flush=True)
                    continue
                selected_repo_paths = batch_repo_paths
                opening_label = ", ".join(repo_path.name for repo_path in selected_repo_paths)
                break

            if choice.isdigit():
                repo_num = int(choice)
                if 1 <= repo_num <= len(repo_paths):
                    selected_repo_paths = [repo_paths[repo_num - 1]]
                    opening_label = selected_repo_paths[0].name
                    break

            print("{red}✗ Invalid selection. Please choose 1-{count}, a, q, or Esc.{reset}".format(
                red=RED,
                count=len(repo_paths),
                reset=RESET,
            ))
            print(prompt, end="", flush=True)

        missing_selected_paths = [str(repo_path) for repo_path in selected_repo_paths if not repo_path.exists()]
        if missing_selected_paths:
            print("\n{red}✗ Repository does not exist:{reset}".format(
                red=RED,
                reset=RESET,
            ))
            for missing_path in missing_selected_paths:
                print("{red}  {path}{reset}".format(red=RED, path=missing_path, reset=RESET))
            wait_for_key()
            return

        print("\nOpening {name} in Kitty...".format(name=opening_label))
        if len(selected_repo_paths) == 1:
            returncode, message = open_repo_in_kitty_tab(selected_repo_paths[0])
        else:
            returncode, message = open_repos_in_kitty_tabs(selected_repo_paths)

        if returncode == 0:
            print("{green}✓ {message}{reset}".format(green=GREEN, message=message, reset=RESET))
        else:
            print("\n{red}✗ Failed to open Kitty / nvim.{reset}".format(red=RED, reset=RESET))
            if message:
                print("{red}  {message}{reset}".format(red=RED, message=message, reset=RESET))

        wait_for_key()
    except Exception as exc:
        print("\n{red}✗ Error: {error}{reset}".format(red=RED, error=exc, reset=RESET))
        wait_for_key()


def run_docker_action(action_key: str) -> tuple:
    """Run a predefined docker maintenance action."""
    action_map = {
        "p": (["docker", "container", "prune", "-f"], "Pruned stopped containers"),
        "i": (["docker", "image", "prune", "-f"], "Pruned dangling images"),
        "n": (["docker", "network", "prune", "-f"], "Pruned unused networks"),
        "v": (["docker", "volume", "prune", "-f"], "Pruned unused volumes"),
        "a": (["docker", "system", "prune", "-f"], "Pruned unused docker resources"),
    }

    if action_key not in action_map:
        return False, "Unknown action"

    command, success_label = action_map[action_key]
    returncode, stdout, stderr = run_command(command)
    output = (stdout or stderr or "").strip()

    if returncode != 0:
        return False, output if output else "Docker action failed"

    if output:
        return True, "{label}\n{output}".format(label=success_label, output=output)
    return True, success_label


def option_7_show_docker_info(config: AppConfig, state: AppState) -> None:
    """Option 7: Show a docker overview plus one-key cleanup actions."""
    if shutil.which("docker") is None:
        clear_screen()
        print("~" * 60)
        print("  {orange}DOCKER CONTAINER INFO{reset}".format(orange=ORANGE, reset=RESET))
        print("~" * 60)
        print()
        print("{red}✗ Docker CLI not found in PATH.{reset}".format(red=RED, reset=RESET))
        print("{yellow}Install Docker Desktop or Docker CLI to use this option.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        wait_for_key()
        return

    action_feedback = ""

    while True:
        clear_screen()
        print("~" * 60)
        print("  {orange}DOCKER CONTAINER INFO{reset}".format(orange=ORANGE, reset=RESET))
        print("~" * 60)
        print()
        print("[p] prune stopped  [i] prune images  [n] prune networks  [v] prune volumes  [a] system prune  [q/esc] back")
        print()

        returncode, _, stderr = run_command(["docker", "info"])
        if returncode != 0:
            print("{red}✗ Docker is not available.{reset}".format(red=RED, reset=RESET))
            print("{yellow}Make sure Docker Desktop/daemon is running.{reset}".format(
                yellow=YELLOW,
                reset=RESET,
            ))
            if stderr.strip():
                print("\n{red}{stderr}{reset}".format(red=RED, stderr=stderr.strip(), reset=RESET))
            print("\nPress q or Esc to return: ", end="", flush=True)
            choice = get_single_char()
            print()
            if choice in ("q", "Q", "\x1b"):
                return
            continue

        rc_running, running_count, running_err = run_command(["docker", "ps", "-q"])
        rc_all, all_count, all_err = run_command(["docker", "ps", "-aq"])

        if rc_running == 0 and rc_all == 0:
            running_total = len([line for line in running_count.splitlines() if line.strip()])
            all_total = len([line for line in all_count.splitlines() if line.strip()])
            stopped_total = max(all_total - running_total, 0)
            print("Running: {green}{running}{reset}   Stopped: {yellow}{stopped}{reset}   Total: {total}".format(
                green=GREEN,
                running=running_total,
                reset=RESET,
                yellow=YELLOW,
                stopped=stopped_total,
                total=all_total,
            ))
            print()
        elif running_err.strip() or all_err.strip():
            print("{yellow}⚠️  Could not compute container counts.{reset}".format(
                yellow=YELLOW,
                reset=RESET,
            ))
            print()

        format_string = "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Label \"com.docker.compose.project\"}}"
        rc, output, err = run_command(["docker", "ps", "-a", "--format", format_string])

        if rc != 0:
            print("{red}✗ Failed to list containers.{reset}".format(red=RED, reset=RESET))
            if err.strip():
                print("{red}{err}{reset}".format(red=RED, err=err.strip(), reset=RESET))
        else:
            rows = [line for line in output.splitlines() if line.strip()]
            if not rows:
                print("{yellow}No containers found.{reset}".format(yellow=YELLOW, reset=RESET))
            else:
                headers = ["Name", "Image", "Status", "Ports", "Compose"]
                table_rows = []
                for row in rows:
                    parts = row.split("\t")
                    while len(parts) < 5:
                        parts.append("")
                    name, image, status, ports, compose_project = parts[:5]
                    ports = ports or "-"
                    compose_project = compose_project or "-"
                    table_rows.append([name, image, status, ports, compose_project])
                print_fixed_width_table(headers, table_rows)

        if action_feedback:
            print("\n{feedback}".format(feedback=action_feedback))
            action_feedback = ""

        print("\nAction: ", end="", flush=True)
        choice = get_single_char().lower()
        if choice in ("q", "\x1b"):
            print()
            return
        print(choice)

        if choice in ("p", "i", "n", "v", "a"):
            ok, message = run_docker_action(choice)
            if ok:
                action_feedback = "{green}✓ {message}{reset}".format(
                    green=GREEN,
                    message=message,
                    reset=RESET,
                )
            else:
                action_feedback = "{red}✗ {message}{reset}".format(
                    red=RED,
                    message=message,
                    reset=RESET,
                )
        else:
            action_feedback = "{yellow}⚠️  Invalid action. Use p/i/n/v/a, q, or Esc.{reset}".format(
                yellow=YELLOW,
                reset=RESET,
            )


def option_9_create_branches(config: AppConfig, state: AppState) -> None:
    """Option 9: Create and checkout new branches across repositories."""
    clear_screen()
    print("~" * 60)
    print("  {orange}CREATE NEW BRANCHES{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print("\nFor each repository:")
    print("  • Select source branch with fuzzy finder (current branch pre-selected)")
    print("  • Enter a name for the new branch")
    print("  • Create and checkout the new branch from the source branch")
    print("\nPress Esc at the branch picker to skip a repository.")
    print()

    if shutil.which("fzf") is None:
        print("{red}✗ fzf is not installed or not in PATH.{reset}".format(red=RED, reset=RESET))
        print("{yellow}Install fzf to use this option.{reset}".format(yellow=YELLOW, reset=RESET))
        wait_for_key()
        return

    summary = []
    last_branch_name = None
    repo_paths = config.repo_paths_for_group(state.active_worktree_group)

    for repo_path in repo_paths:
        if not repo_path.exists():
            summary.append({"repo": repo_path.name, "status": "skipped", "detail": "Repository not found"})
            continue

        print("\n📁 {repo}".format(repo=repo_path.name))
        print("-" * 60)

        returncode, status_output, _ = run_git_command(
            repo_path,
            ["git", "status", "--short"],
            show_output=False,
        )
        if returncode == 0 and status_output.strip():
            print("  {yellow}⚠️  Skipping: repository has uncommitted changes{reset}".format(
                yellow=YELLOW,
                reset=RESET,
            ))
            summary.append({"repo": repo_path.name, "status": "skipped", "detail": "Uncommitted changes"})
            continue

        returncode, current_branch_raw, _ = run_git_command(
            repo_path,
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            show_output=False,
        )
        current_branch = current_branch_raw.strip() if returncode == 0 else ""
        if current_branch:
            print("  Current branch: {orange}{branch}{reset}".format(
                orange=ORANGE,
                branch=current_branch,
                reset=RESET,
            ))

        print("  Select source branch...")
        try:
            selected, source_branch = pick_source_branch_with_fzf(repo_path, current_branch)
        except RuntimeError as exc:
            print("  {red}✗ {error}{reset}".format(red=RED, error=exc, reset=RESET))
            summary.append({"repo": repo_path.name, "status": "error", "detail": str(exc)})
            continue

        if not selected:
            print("  {dim}Skipped{reset}".format(dim=DIM, reset=RESET))
            summary.append({"repo": repo_path.name, "status": "skipped", "detail": "Skipped, no changes"})
            continue

        print("  Selected source branch: {orange}{branch}{reset}".format(
            orange=ORANGE,
            branch=source_branch,
            reset=RESET,
        ))
        print()

        if last_branch_name:
            new_branch_name = input_with_default(
                "  New branch name [{default}]: ".format(default=last_branch_name),
                last_branch_name,
            ).strip()
            if not new_branch_name:
                new_branch_name = last_branch_name
        else:
            new_branch_name = input("  New branch name: ").strip()

        if not new_branch_name:
            print("  {yellow}⚠️  Skipping: no branch name provided{reset}".format(
                yellow=YELLOW,
                reset=RESET,
            ))
            summary.append({"repo": repo_path.name, "status": "skipped", "detail": "No branch name provided"})
            continue

        print("  • Checking out source branch '{branch}'...".format(branch=source_branch))
        returncode, _, stderr = run_git_command(
            repo_path,
            ["git", "checkout", source_branch],
            show_output=False,
        )
        if returncode != 0:
            err = stderr.strip()
            print("  {red}✗ Failed to checkout source branch: {err}{reset}".format(
                red=RED,
                err=err,
                reset=RESET,
            ))
            summary.append({
                "repo": repo_path.name,
                "status": "error",
                "detail": "Failed to checkout {branch}: {err}".format(branch=source_branch, err=err),
            })
            continue

        print("  • Creating and checking out '{branch}'...".format(branch=new_branch_name))
        returncode, _, stderr = run_git_command(
            repo_path,
            ["git", "checkout", "-b", new_branch_name],
            show_output=False,
        )
        if returncode != 0:
            err = stderr.strip()
            print("  {red}✗ Failed to create branch: {err}{reset}".format(red=RED, err=err, reset=RESET))
            summary.append({
                "repo": repo_path.name,
                "status": "error",
                "detail": "Failed to create {branch}: {err}".format(branch=new_branch_name, err=err),
            })
            continue

        print("  {green}✓ Created and checked out '{new}' from '{source}'{reset}".format(
            green=GREEN,
            new=new_branch_name,
            source=source_branch,
            reset=RESET,
        ))
        last_branch_name = new_branch_name
        summary.append({
            "repo": repo_path.name,
            "status": "created",
            "detail": "{source} → {new}".format(source=source_branch, new=new_branch_name),
        })

    print("\n" + "~" * 60)
    print("  {orange}SUMMARY{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    for entry in summary:
        if entry["status"] == "created":
            print("  {green}✓ {repo}{reset}: {detail}".format(
                green=GREEN,
                repo=entry["repo"],
                reset=RESET,
                detail=entry["detail"],
            ))
        elif entry["status"] == "error":
            print("  {red}✗ {repo}{reset}: {detail}".format(
                red=RED,
                repo=entry["repo"],
                reset=RESET,
                detail=entry["detail"],
            ))
        else:
            print("  {dim}— {repo}{reset}: {detail}".format(
                dim=DIM,
                repo=entry["repo"],
                reset=RESET,
                detail=entry["detail"],
            ))

    wait_for_key()


def run_app(config: AppConfig, state: AppState) -> None:
    """Main application loop."""
    clear_screen()
    print("Validating repositories...\n")
    if not validate_repos(config):
        print("\n{red}✗ Exiting due to repository validation issues.{reset}".format(red=RED, reset=RESET))
        sys.exit(1)

    worktrees.initialise_active_worktree_group(config, state)

    while True:
        show_menu(config, state)

        try:
            print("\nSelect option (1-9, w, q to quit): ", end="", flush=True)
            choice = get_single_char()
            print()

            if choice == "1":
                option_1_show_status(config, state)
            elif choice == "2":
                option_2_reset_to_main(config, state)
            elif choice == "3":
                option_3_stash_to_main(config, state)
            elif choice == "4":
                option_4_checkout_branches(config, state)
            elif choice == "5":
                option_5_run_make_command(config, state)
            elif choice == "6":
                option_6_open_in_code_editor(config, state)
            elif choice == "7":
                option_7_show_docker_info(config, state)
            elif choice == "8":
                state.show_notifications = not state.show_notifications
                if state.show_notifications:
                    dashboard.run_cache_fetch(config, state)
            elif choice == "9":
                option_9_create_branches(config, state)
            elif choice in ("w", "W"):
                worktrees.option_w_worktrees(config, state)
            elif choice in ("q", "Q", "\x1b"):
                clear_screen()
                print("Goodbye! 👋")
                sys.exit(0)
            else:
                print("\n{red}✗ Invalid option. Please select 1-9 or w.{reset}".format(red=RED, reset=RESET))
                wait_for_key()
        except KeyboardInterrupt:
            clear_screen()
            print("\n\nInterrupted by user. Goodbye! 👋")
            sys.exit(0)
        except Exception as exc:
            print("\n{red}✗ Unexpected error: {error}{reset}".format(red=RED, error=exc, reset=RESET))
            wait_for_key()
