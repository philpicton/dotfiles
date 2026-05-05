"""Worktree-group discovery, lifecycle, and docker switching behaviour."""

import fnmatch
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .context import AppConfig, AppState
from .shell import run_command, run_command_in_dir, run_git_command
from .ui import GREEN, ORANGE, RED, RESET, YELLOW, clear_screen, get_single_char, wait_for_key


def validate_worktree_group_name(config: AppConfig, name: str) -> Tuple[bool, str]:
    """Validate a worktree group folder name for macOS/Linux-safe usage."""
    if not name:
        return False, "Group name cannot be empty"
    if name in config.reserved_worktree_group_names:
        return False, "Group name is reserved"
    if name in (".", ".."):
        return False, "Group name is invalid"
    if "/" in name or "\\" in name:
        return False, "Group name cannot contain path separators"

    for ch in name:
        if not (ch.isalnum() or ch in ("-", "_", ".")):
            return False, "Use only letters, numbers, dash, underscore, or dot"

    return True, ""


def get_worktree_paths_for_repo(canonical_repo_path: Path) -> Tuple[bool, Set[Path], str]:
    """Return all known worktree paths for a canonical repository."""
    if not canonical_repo_path.exists():
        return False, set(), "Canonical repo missing: {path}".format(path=canonical_repo_path)

    returncode, stdout, stderr = run_command_in_dir(
        ["git", "worktree", "list", "--porcelain"],
        canonical_repo_path,
    )
    if returncode != 0:
        err = (stderr or stdout or "").strip()
        return False, set(), err or "Failed to list git worktrees"

    worktrees = set()
    for line in stdout.splitlines():
        if line.startswith("worktree "):
            wt_path = line[len("worktree ") :].strip()
            if wt_path:
                worktrees.add(Path(wt_path).expanduser().resolve())

    return True, worktrees, ""


def validate_worktree_group(config: AppConfig, group_name: str) -> Tuple[bool, str]:
    """Strictly validate that a group contains all expected repo worktrees."""
    if group_name == config.main_worktree_group:
        return True, ""

    group_root = config.root_path / group_name
    if group_root.is_symlink():
        return False, "{group}: group folder cannot be a symlink".format(group=group_name)
    if not group_root.exists() or not group_root.is_dir():
        return False, "{group}: group folder is missing".format(group=group_name)

    for repo_rel in config.repo_relative_paths:
        canonical_repo = (config.root_path / repo_rel).resolve()
        target_repo = (group_root / repo_rel).resolve()

        if not target_repo.exists():
            return False, "{group}: missing {repo}".format(group=group_name, repo=repo_rel)
        if not (target_repo / ".git").exists():
            return False, "{group}: {repo} is not a git worktree folder".format(
                group=group_name,
                repo=repo_rel,
            )

        ok, paths, err = get_worktree_paths_for_repo(canonical_repo)
        if not ok:
            return False, "{group}: {repo} worktree check failed ({err})".format(
                group=group_name,
                repo=repo_rel,
                err=err,
            )
        if target_repo not in paths:
            return False, "{group}: {repo} is not registered as a worktree".format(
                group=group_name,
                repo=repo_rel,
            )

    return True, ""


def discover_worktree_groups(config: AppConfig) -> Tuple[List[str], Dict[str, str]]:
    """Discover valid worktree groups and invalid candidate directories under ROOTDIR."""
    valid_groups = [config.main_worktree_group]
    invalid_groups = {}

    if not config.root_path.exists() or not config.root_path.is_dir():
        return valid_groups, invalid_groups

    top_level_repo_roots = {repo.parts[0] for repo in config.repo_relative_paths if repo.parts}

    for child in config.root_path.iterdir():
        if not child.is_dir():
            continue

        name = child.name
        if name in top_level_repo_roots or name.startswith("."):
            continue

        name_ok, _ = validate_worktree_group_name(config, name)
        if not name_ok:
            continue
        if child.is_symlink():
            invalid_groups[name] = "group folder cannot be a symlink"
            continue

        is_valid, reason = validate_worktree_group(config, name)
        if is_valid:
            valid_groups.append(name)
        else:
            invalid_groups[name] = reason

    valid_groups = [config.main_worktree_group] + sorted(
        [group for group in valid_groups if group != config.main_worktree_group]
    )
    return valid_groups, invalid_groups


def save_active_worktree_group(config: AppConfig, group_name: str) -> None:
    """Persist the active worktree group to disk."""
    try:
        config.worktree_state_file.parent.mkdir(parents=True, exist_ok=True)
        config.worktree_state_file.write_text(
            json.dumps({"active_group": group_name}, indent=2),
            encoding="utf-8",
        )
    except Exception:
        # This state file is best-effort. The TUI should keep working without it.
        pass


def load_active_worktree_group(config: AppConfig) -> str:
    """Load the persisted active worktree group from disk."""
    if not config.worktree_state_file.exists():
        return config.main_worktree_group

    try:
        data = json.loads(config.worktree_state_file.read_text(encoding="utf-8"))
        return str(data.get("active_group", config.main_worktree_group))
    except Exception:
        return config.main_worktree_group


def get_groups_with_running_docker_stacks(config: AppConfig, groups: List[str]) -> List[str]:
    """Best-effort detection of worktree groups that currently have running compose services."""
    if shutil.which("docker") is None:
        return []

    running_groups = []
    for group in groups:
        repo_root = config.parent_repo_path_for_group(group)
        if not repo_root.exists():
            continue

        returncode, stdout, _ = run_compose_command(config, group, repo_root, ["ps", "-q"])
        if returncode == 0 and stdout.strip():
            running_groups.append(group)

    return running_groups


def get_group_with_running_docker_stack(config: AppConfig, groups: List[str]) -> Optional[str]:
    """Return the first worktree group with running compose services, if any."""
    running_groups = get_groups_with_running_docker_stacks(config, groups)
    return running_groups[0] if running_groups else None


def stop_other_running_docker_stacks(
    config: AppConfig,
    keep_group: str,
) -> Tuple[List[str], List[str]]:
    """Stop every running worktree stack except the one we want to keep.

    This protects host-bound local services such as nginx, MySQL, mail, and
    supervisor from fighting over ports when the user switches groups or runs a
    stack-changing make target inside one worktree group.
    """
    groups, _ = discover_worktree_groups(config)
    running_groups = get_groups_with_running_docker_stacks(config, groups)

    stopped_groups: List[str] = []
    warnings: List[str] = []

    for group in running_groups:
        if group == keep_group:
            continue

        repo_root = config.parent_repo_path_for_group(group)
        ok, message = run_docker_stack_down(config, group, repo_root)
        if ok:
            stopped_groups.append(group)
        else:
            warnings.append(
                "Failed to bring docker down for group '{group}': {message}".format(
                    group=group,
                    message=message,
                )
            )

    return stopped_groups, warnings


def _normalise_compose_fragment(value: str) -> str:
    """Map group and repo names to a docker-compose-safe project fragment."""
    cleaned = []
    for char in value.lower():
        if char.isalnum() or char in ("-", "_"):
            cleaned.append(char)
        else:
            cleaned.append("-")
    fragment = "".join(cleaned).strip("-_")
    return fragment or "repo-man"


def get_worktree_branch_name(config: AppConfig, group_name: str) -> str:
    """Return the synthetic branch name used to anchor one worktree group."""
    return config.worktree_branch_name(group_name)


def get_compose_project_name(config: AppConfig, group_name: str, repo_root: Path) -> str:
    """Build the compose project name used for one worktree group's containers."""
    repo_fragment = _normalise_compose_fragment(repo_root.name)
    if group_name == config.main_worktree_group:
        return repo_fragment
    return "{group}-{repo}".format(
        group=_normalise_compose_fragment(group_name),
        repo=repo_fragment,
    )


def build_compose_environment(config: AppConfig, group_name: str, repo_root: Path) -> Dict[str, str]:
    """Provide a compose environment that scopes containers to the active group."""
    env = os.environ.copy()
    # Keep compose profile selection in the environment too, so user-triggered
    # commands like `make restart` or `make down` manage the same local-only
    # services as repo-man's own docker switching helpers.
    env["COMPOSE_PROFILES"] = "local"
    # Keep the main group on docker compose's default project naming so it
    # continues to use the same containers it used before worktree support.
    if group_name == config.main_worktree_group:
        env.pop("COMPOSE_PROJECT_NAME", None)
        return env

    env["COMPOSE_PROJECT_NAME"] = get_compose_project_name(config, group_name, repo_root)
    return env


def get_compose_command(config: AppConfig, group_name: str) -> List[str]:
    """Build the docker compose command for one worktree group.

    Repo-man always opts into the local profile so switching groups manages the
    full local stack, including profile-only services such as MySQL and mail.
    The main group still keeps docker compose's original project name so it
    continues to use the same container names and volumes as before.
    """
    return ["docker", "compose", "--profile", "local"]


def run_compose_command(
    config: AppConfig,
    group_name: str,
    repo_root: Path,
    compose_args: List[str],
) -> Tuple[int, str, str]:
    """Run docker compose using the group-specific project name."""
    try:
        result = subprocess.run(
            [*get_compose_command(config, group_name), *compose_args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            env=build_compose_environment(config, group_name, repo_root),
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as exc:
        return 1, "", str(exc)


def run_group_command_streaming(
    config: AppConfig,
    group_name: str,
    repo_root: Path,
    command: List[str],
    extra_env: Optional[Dict[str, str]] = None,
) -> Tuple[bool, str]:
    """Run a worktree-scoped command while streaming output to the TUI."""
    env = build_compose_environment(config, group_name, repo_root)
    if extra_env:
        env.update(extra_env)

    try:
        result = subprocess.run(command, cwd=repo_root, env=env)
    except Exception as exc:
        return False, str(exc)

    if result.returncode != 0:
        return False, "Command failed with exit code {code}: {command}".format(
            code=result.returncode,
            command=" ".join(command),
        )
    return True, ""


def initialise_active_worktree_group(config: AppConfig, state: AppState) -> None:
    """Load and validate the active worktree group, warning on mismatches."""
    persisted = load_active_worktree_group(config)
    valid_groups, _ = discover_worktree_groups(config)

    if persisted in valid_groups:
        state.active_worktree_group = persisted
    else:
        state.active_worktree_group = config.main_worktree_group
        if persisted != config.main_worktree_group:
            state.startup_notice = (
                "{yellow}⚠️  Saved worktree group '{group}' is no longer valid. "
                "Falling back to '{fallback}'.{reset}"
            ).format(
                yellow=YELLOW,
                group=persisted,
                fallback=config.main_worktree_group,
                reset=RESET,
            )
        save_active_worktree_group(config, state.active_worktree_group)

    running_group = get_group_with_running_docker_stack(config, valid_groups)
    if running_group and running_group != state.active_worktree_group:
        mismatch = (
            "{yellow}⚠️  Docker appears active for group '{running}', "
            "but repo-man is set to '{active}'.{reset}"
        ).format(
            yellow=YELLOW,
            running=running_group,
            active=state.active_worktree_group,
            reset=RESET,
        )
        if state.startup_notice:
            state.startup_notice = "{first}\n{second}".format(
                first=state.startup_notice,
                second=mismatch,
            )
        else:
            state.startup_notice = mismatch


def run_docker_stack_down(config: AppConfig, group_name: str, repo_root: Path) -> Tuple[bool, str]:
    """Bring docker compose down for a repository root."""
    if shutil.which("docker") is None:
        return False, "Docker CLI not found"
    if not repo_root.exists():
        return False, "Repo root not found: {repo_root}".format(repo_root=repo_root)

    returncode, stdout, stderr = run_compose_command(config, group_name, repo_root, ["down"])
    if returncode != 0:
        return False, (stderr or stdout or "docker compose down failed").strip()
    return True, (stdout or "docker compose down complete").strip()


def _run_worktree_api_composer_install(
    config: AppConfig,
    group_name: str,
    repo_root: Path,
) -> Tuple[int, str, str]:
    """Run the worktree API's Composer install command inside the container."""
    return run_compose_command(
        config,
        group_name,
        repo_root,
        [
            "exec",
            "-T",
            "haysto-api",
            "composer",
            "install",
            "--no-interaction",
            "--no-scripts",
        ],
    )


def _is_composer_archive_extract_failure(output: str) -> bool:
    """Return True when Composer failed while extracting a downloaded package archive."""
    archive_error_markers = (
        "Failed to extract",
        "ZipDownloader.php",
        "invalid compressed data to inflate",
        'mismatching "local" filename',
    )
    return any(marker in output for marker in archive_error_markers)


def _recover_worktree_api_composer_state(
    config: AppConfig,
    group_name: str,
    repo_root: Path,
) -> Tuple[bool, str]:
    """Clear partial Composer state so one retry can redownload clean archives.

    Fresh worktrees sometimes hit a corrupted package download or half-extracted
    archive while the API container performs its first dependency install.
    Clearing Composer's cache plus the worktree-local vendor/composer metadata
    gives the retry a clean slate without touching tracked files.
    """
    clear_returncode, clear_stdout, clear_stderr = run_compose_command(
        config,
        group_name,
        repo_root,
        [
            "exec",
            "-T",
            "haysto-api",
            "composer",
            "clear-cache",
        ],
    )
    if clear_returncode != 0:
        return False, (clear_stderr or clear_stdout or "composer clear-cache failed").strip()

    cleanup_returncode, cleanup_stdout, cleanup_stderr = run_compose_command(
        config,
        group_name,
        repo_root,
        [
            "exec",
            "-T",
            "haysto-api",
            "sh",
            "-lc",
            "rm -rf vendor/composer",
        ],
    )
    if cleanup_returncode != 0:
        return False, (cleanup_stderr or cleanup_stdout or "failed cleaning vendor/composer").strip()

    return True, "cleared composer cache and vendor/composer"


def refresh_worktree_api_dependencies(
    config: AppConfig,
    group_name: str,
    repo_root: Path,
) -> Tuple[bool, str]:
    """Refresh Composer dependencies for non-main worktree API stacks.

    Worktree creation can carry across selected ignored local config such as
    `.env` files, but dependencies are installed fresh inside each worktree.
    Refreshing dependencies inside the worktree API container keeps the cloned
    stack aligned without touching the original maintained worktree. We skip
    Composer scripts here because worktree `.git` files point back to host-side
    gitdirs that are not visible inside the container.
    """
    if group_name == config.main_worktree_group:
        return True, ""

    api_repo = repo_root / "haysto-v2-api"
    composer_manifest = api_repo / "composer.json"
    if not composer_manifest.exists():
        return True, ""

    returncode, stdout, stderr = _run_worktree_api_composer_install(
        config,
        group_name,
        repo_root,
    )
    if returncode != 0:
        install_error = (stderr or stdout or "composer install failed").strip()
        if not _is_composer_archive_extract_failure(install_error):
            return False, install_error

        recovered, recovery_message = _recover_worktree_api_composer_state(
            config,
            group_name,
            repo_root,
        )
        if not recovered:
            return False, "{error}\nRecovery failed: {recovery}".format(
                error=install_error,
                recovery=recovery_message,
            )

        retry_returncode, retry_stdout, retry_stderr = _run_worktree_api_composer_install(
            config,
            group_name,
            repo_root,
        )
        if retry_returncode != 0:
            retry_error = (retry_stderr or retry_stdout or "composer install retry failed").strip()
            return False, "{error}\nRetried after {recovery}, but install still failed: {retry}".format(
                error=install_error,
                recovery=recovery_message,
                retry=retry_error,
            )
        return True, "composer install succeeded after retrying with cleaned cache state"
    return True, (stdout or "composer install complete").strip()


def run_docker_stack_up(config: AppConfig, group_name: str, repo_root: Path) -> Tuple[bool, str]:
    """Bring docker compose up for a repository root."""
    if shutil.which("docker") is None:
        return False, "Docker CLI not found"
    if not repo_root.exists():
        return False, "Repo root not found: {repo_root}".format(repo_root=repo_root)

    returncode, stdout, stderr = run_compose_command(config, group_name, repo_root, ["up", "-d"])
    if returncode != 0:
        return False, (stderr or stdout or "docker compose up -d failed").strip()
    return True, (stdout or "docker compose up -d complete").strip()


def worktree_group_requires_initialisation(config: AppConfig, group_name: str) -> bool:
    """Return True when a non-main group is missing first-run bootstrap output.

    Repo-man's worktree init is modelled on `make init`, which installs frontend
    node modules before starting the app stack and refreshes API Composer
    dependencies after startup. If we start the stack for a fresh worktree too
    early, the Nuxt containers can generate partial state against missing
    dependencies and poison the first bootstrap.
    """
    if group_name == config.main_worktree_group:
        return False

    repo_root = config.parent_repo_path_for_group(group_name)
    required_paths = (
        repo_root / "haysto-v2-create" / "node_modules",
        repo_root / "haysto-v2-collect" / "node_modules",
        repo_root / "haysto-v2-dev" / "node_modules",
        repo_root / "haysto-v2-collaborate" / "node_modules",
        repo_root / "lib/js/haysto-v2-lib_shared" / "node_modules",
        repo_root / "haysto-v2-api" / "vendor",
    )
    return any(not path.exists() for path in required_paths)


def initialise_worktree_group_stack(config: AppConfig, group_name: str) -> Tuple[bool, List[str]]:
    """Run the worktree-safe equivalent of `make init` for one non-main group."""
    warnings: List[str] = []
    if group_name == config.main_worktree_group:
        return False, ["Use option 5's normal make init command for the main group."]

    is_valid, reason = validate_worktree_group(config, group_name)
    if not is_valid:
        return False, [reason]

    repo_root = config.parent_repo_path_for_group(group_name)
    stopped_groups, stop_warnings = stop_other_running_docker_stacks(config, group_name)
    warnings.extend(stop_warnings)
    for stopped_group in stopped_groups:
        warnings.append("Stopped docker stack for group '{group}'.".format(group=stopped_group))

    print("\n{orange}→ Building containers for '{group}'...{reset}".format(
        orange=ORANGE,
        group=group_name,
        reset=RESET,
    ))
    ok, message = run_group_command_streaming(
        config,
        group_name,
        repo_root,
        [*get_compose_command(config, group_name), "build", "--build-arg", "INSTALL_XDEBUG=true"],
        extra_env={"DOCKER_BUILDKIT": "1"},
    )
    if not ok:
        return False, warnings + [message]

    print("\n{orange}→ Installing frontend node modules...{reset}".format(
        orange=ORANGE,
        reset=RESET,
    ))
    ok, message = run_group_command_streaming(
        config,
        group_name,
        repo_root,
        ["node", "./node-modules-manager.mjs", "--install-all"],
    )
    if not ok:
        return False, warnings + [message]

    print("\n{orange}→ Starting docker stack...{reset}".format(orange=ORANGE, reset=RESET))
    ok, message = run_docker_stack_up(config, group_name, repo_root)
    if not ok:
        return False, warnings + [message]

    print("\n{orange}→ Refreshing API Composer dependencies...{reset}".format(
        orange=ORANGE,
        reset=RESET,
    ))
    deps_ok, deps_message = refresh_worktree_api_dependencies(config, group_name, repo_root)
    if not deps_ok:
        return False, warnings + [deps_message]

    api_repo = repo_root / "haysto-v2-api"
    api_env = api_repo / ".env"
    api_env_example = api_repo / ".env.example"
    if not api_env.exists() and api_env_example.exists():
        print("\n{orange}→ Creating API .env and generating app key...{reset}".format(
            orange=ORANGE,
            reset=RESET,
        ))
        shutil.copy2(api_env_example, api_env)
        ok, message = run_group_command_streaming(
            config,
            group_name,
            repo_root,
            [*get_compose_command(config, group_name), "exec", "-T", "haysto-api", "php", "artisan", "key:generate"],
        )
        if not ok:
            return False, warnings + [message]

    print("\n{orange}→ Updating API storage permissions...{reset}".format(
        orange=ORANGE,
        reset=RESET,
    ))
    ok, message = run_group_command_streaming(
        config,
        group_name,
        repo_root,
        [*get_compose_command(config, group_name), "exec", "-T", "-u", "root", "haysto-api", "chmod", "-R", "777", "storage"],
    )
    if not ok:
        return False, warnings + [message]

    return True, warnings


def set_active_worktree_group(config: AppConfig, state: AppState, target_group: str) -> List[str]:
    """Switch the active group and warn rather than fail on docker issues."""
    print(
        "\n{orange}→ Stopping other running worktree stacks...{reset}".format(
            orange=ORANGE,
            reset=RESET,
        ),
        flush=True,
    )
    _, warnings = stop_other_running_docker_stacks(config, target_group)

    print(
        "{orange}→ Saving active worktree selection...{reset}".format(
            orange=ORANGE,
            reset=RESET,
        ),
        flush=True,
    )
    state.active_worktree_group = target_group
    save_active_worktree_group(config, target_group)

    target_root = config.parent_repo_path_for_group(state.active_worktree_group)
    if worktree_group_requires_initialisation(config, state.active_worktree_group):
        print(
            "{orange}→ '{group}' still needs its first initialisation, so repo-man is leaving the stack stopped for now.{reset}".format(
                orange=ORANGE,
                group=state.active_worktree_group,
                reset=RESET,
            ),
            flush=True,
        )
        warnings.append(
            "Skipped docker startup for '{group}' because it has not been initialised yet. "
            "Run 'Initialise active worktree' so it follows the normal make init order "
            "(build, install dependencies, start stack, refresh Composer).".format(
                group=state.active_worktree_group,
            )
        )
        return warnings

    print(
        "{orange}→ Starting docker stack for '{group}'...{reset}".format(
            orange=ORANGE,
            group=state.active_worktree_group,
            reset=RESET,
        ),
        flush=True,
    )
    ok, message = run_docker_stack_up(config, state.active_worktree_group, target_root)
    if not ok:
        warnings.append("Failed to bring docker up for new group: {message}".format(message=message))

    return warnings


def reset_active_group_to_main(config: AppConfig, state: AppState) -> Tuple[bool, str]:
    """Move repo-man back to the canonical group after an active-group failure."""
    state.active_worktree_group = config.main_worktree_group
    save_active_worktree_group(config, state.active_worktree_group)
    return run_docker_stack_up(
        config,
        state.active_worktree_group,
        config.parent_repo_path_for_group(state.active_worktree_group),
    )


def show_worktrees_help(config: AppConfig) -> None:
    """Show the worktree-group help page."""
    clear_screen()
    print("~" * 60)
    print("  {orange}WORKTREES HELP{reset}".format(orange=ORANGE, reset=RESET))
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
    print("  {root}/".format(root=config.root_path))
    print("    haysto-v2/                (main group parent repo)")
    print("    enquiry-form/")
    print("    <group-name>/")
    print("      haysto-v2/")
    print("      enquiry-form/")
    print()
    print("What Repo-man does:")
    print("  • Create group: ")
    print("     - Creates a new worktree group in a folder with the name you give it.")
    print("     - Then in the new worktrees, creates a branch like `{branch}`".format(
        branch=get_worktree_branch_name(config, "<group>"),
    ))
    print("       from `main` for each repo.")
    print("       NB. You can't have the same branch checked out in multiple worktrees,")
    print("       so we must create a new branch per repo for each group.")
    print("     - Then sets upstream to origin/main and pulls with --ff-only. ")
    print("     - It also copies over selected gitignored local config files")
    print("       from the allowlist in repo-man.py, such as .env and .env.*.")
    print("       Dependencies and generated build artifacts are not copied.")
    print("     - And recreates the shared-lib symlinks inside the new worktree repos.")
    print("     - New groups get their own docker project naming and, when started, their own")
    print("       local-profile services such as nginx, MySQL, mail, redis, and supervisor.")
    print("     - Refreshes the API Composer autoload data for non-main groups after")
    print("       startup, but it does NOT initialise the new database for you.")
    print("     - After creating and switching to a new group, use this menu's")
    print("       'Initialise active worktree' action, then use option 5's worktree")
    print("       database bootstrap command to initialise schema and seed data.")
    print("    ⚠️ Probably avoid committing to the new branch and pushing! Create/checkout new branches.")
    print()
    print("  • Switch group: ")
    print("     - brings down any other running worktree stacks, then runs")
    print("       `docker compose up` for the new group once that group has already been")
    print("       initialised. Fresh groups are marked active first and left stopped so")
    print("       their first bootstrap can follow the normal make init order.")
    print("     - The main group keeps the")
    print("       original compose/container naming, while non-main groups use a compose project name")
    print("       prefixed by the worktree group so they get their own containers and volumes.")
    print("     - Uses the local compose profile for docker switching so each group brings")
    print("       up the full local stack, including MySQL/mail where the compose file defines them,")
    print("       but fresh groups skip this until initialisation completes.")
    print("     - Switching never runs the API Composer refresh. That happens during")
    print("       'Initialise active worktree'.")
    print("     - Checks which docker stacks are currently running so it can show the")
    print("       docker-active worktree in the menu, and persists the active group in project root.")
    print()
    print("  • Initialise active worktree: ")
    print("     - Runs the worktree-safe equivalent of `make init` for the currently active")
    print("       non-main group.")
    print("     - Builds containers, installs node modules, starts the stack, refreshes API")
    print("       Composer dependencies, and fixes API storage permissions.")
    print("     - It does NOT initialise the database; use option 5's worktree database")
    print("       bootstrap command afterwards.")
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
    print("  • The original haysto-v2 worktree is protected from deletion and") 
    print("    worktree functionality in this app should not alter it.")
    print()
    wait_for_key()


def option_worktrees_list_groups(config: AppConfig, state: AppState) -> None:
    """List valid worktree groups and invalid candidate folders."""
    clear_screen()
    print("~" * 60)
    print("  {orange}WORKTREE GROUPS{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print()

    groups, invalid = discover_worktree_groups(config)
    for group in groups:
        marker = ""
        if group == config.main_worktree_group:
            marker = " (main)"
        if group == state.active_worktree_group:
            marker = "{marker} (active)".format(marker=marker)
        print("  {green}✓ {group}{reset}{marker}".format(
            green=GREEN,
            group=group,
            reset=RESET,
            marker=marker,
        ))

    if invalid:
        print("\n{yellow}Invalid candidates (not usable groups):{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        for name, reason in sorted(invalid.items()):
            print("  {red}✗ {name}{reset}: {reason}".format(
                red=RED,
                name=name,
                reset=RESET,
                reason=reason,
            ))

    wait_for_key()


def should_copy_gitignored_file(config: AppConfig, relative_path: str) -> bool:
    """Return True when an ignored path matches the configured worktree allowlist."""
    normalized_path = relative_path.replace("\\", "/")
    basename = Path(relative_path).name
    for pattern in config.worktree_gitignored_copy_patterns:
        if fnmatch.fnmatch(normalized_path, pattern) or fnmatch.fnmatch(basename, pattern):
            return True
    return False


def copy_gitignored_files(
    config: AppConfig,
    canonical_repo: Path,
    target_repo: Path,
) -> Tuple[int, List[str]]:
    """Copy allowlisted gitignored files from the canonical repo into the new worktree."""
    result = subprocess.run(
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "-z"],
        cwd=canonical_repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return 0, ["git ls-files failed: {stderr}".format(stderr=result.stderr.strip())]

    files = [filename for filename in result.stdout.split("\0") if filename]
    copied = 0
    errors = []

    for rel in files:
        if not should_copy_gitignored_file(config, rel):
            continue
        src = canonical_repo / rel
        if not src.is_file() and not src.is_symlink():
            continue
        dst = target_repo / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Preserve symlinks exactly as they exist in the source worktree.
            # Flattening a symlink into a plain file can change relative lookup
            # behaviour and break local tooling in the new worktree.
            if src.is_symlink():
                if dst.exists() or dst.is_symlink():
                    if dst.is_dir() and not dst.is_symlink():
                        raise OSError(
                            "Refusing to replace existing directory with symlink: {path}".format(
                                path=dst
                            )
                        )
                    dst.unlink()
                dst.symlink_to(os.readlink(src))
            else:
                shutil.copy2(src, dst)
            copied += 1
        except Exception as exc:
            errors.append("{rel}: {error}".format(rel=rel, error=exc))

    return copied, errors


def ensure_group_symlink(link_path: Path, target_path: Path) -> Tuple[bool, str]:
    """Recreate one worktree symlink without deleting unexpected real content."""
    if link_path.exists() or link_path.is_symlink():
        if link_path.is_symlink():
            link_path.unlink()
        elif link_path.is_dir():
            try:
                link_path.rmdir()
            except OSError:
                return False, "Refusing to replace non-empty directory: {path}".format(path=link_path)
        else:
            return False, "Refusing to replace non-symlink path: {path}".format(path=link_path)

    link_path.parent.mkdir(parents=True, exist_ok=True)
    relative_target = os.path.relpath(target_path, start=link_path.parent)
    link_path.symlink_to(relative_target)
    return True, "linked to {target}".format(target=relative_target)


def recreate_group_shared_lib_symlinks(config: AppConfig, group_root: Path) -> List[Tuple[str, str, str]]:
    """Recreate the cross-repo shared-lib symlinks inside one worktree group."""
    parent_root = group_root / config.main_worktree_folder_name
    shared_lib_repo = parent_root / "lib/js/haysto-v2-lib_shared"
    symlink_targets = [
        parent_root / "haysto-v2-create/lib/js/haysto-v2-lib_shared",
        parent_root / "haysto-v2-collect/lib/js/haysto-v2-lib_shared",
    ]

    if not shared_lib_repo.exists():
        return [("shared-lib", "error", "Shared lib repo missing: {path}".format(path=shared_lib_repo))]

    results = []
    for link_path in symlink_targets:
        ok, message = ensure_group_symlink(link_path, shared_lib_repo)
        results.append((str(link_path.relative_to(group_root)), "ok" if ok else "error", message))
    return results


def option_worktrees_create_group(config: AppConfig, state: AppState) -> None:
    """Create a new worktree group for all managed repositories."""
    clear_screen()
    print("~" * 60)
    print("  {orange}CREATE WORKTREE GROUP{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print()

    group_name = input("New worktree group name: ").strip()
    is_valid, reason = validate_worktree_group_name(config, group_name)
    if not is_valid:
        print("\n{red}✗ Invalid group name: {reason}{reset}".format(
            red=RED,
            reason=reason,
            reset=RESET,
        ))
        wait_for_key()
        return

    group_root = config.root_path / group_name
    if group_root.exists():
        print("\n{red}✗ Group folder already exists: {path}{reset}".format(
            red=RED,
            path=group_root,
            reset=RESET,
        ))
        wait_for_key()
        return

    print("\nCreating worktree group {orange}{group}{reset}...".format(
        orange=ORANGE,
        group=group_name,
        reset=RESET,
    ))

    summary = []
    all_ok = True
    worktree_branch = get_worktree_branch_name(config, group_name)

    total_repos = len(config.repo_relative_paths)
    for index, repo_rel in enumerate(config.repo_relative_paths, start=1):
        canonical_repo = (config.root_path / repo_rel).resolve()
        target_repo = (group_root / repo_rel).resolve()

        print(
            "{orange}→ [{index}/{total}] Preparing {repo}...{reset}".format(
                orange=ORANGE,
                index=index,
                total=total_repos,
                repo=repo_rel,
                reset=RESET,
            ),
            flush=True,
        )

        if not canonical_repo.exists() or not (canonical_repo / ".git").exists():
            all_ok = False
            summary.append((str(repo_rel), "error", "Canonical repo missing or invalid"))
            continue

        if target_repo.exists():
            all_ok = False
            summary.append((str(repo_rel), "error", "Target path already exists"))
            continue

        target_repo.parent.mkdir(parents=True, exist_ok=True)

        # Prune first so a stale worktree entry does not block a recreated group.
        run_git_command(
            canonical_repo,
            ["git", "worktree", "prune", "--expire", "now"],
            show_output=False,
        )

        # Refuse to reuse an existing synthetic branch name. Using `-B` here
        # would reset that branch back to main and could destroy committed work.
        branch_exists_code, _, branch_exists_err = run_git_command(
            canonical_repo,
            ["git", "show-ref", "--verify", "--quiet", "refs/heads/{branch}".format(branch=worktree_branch)],
            show_output=False,
        )
        if branch_exists_code == 0:
            all_ok = False
            summary.append((str(repo_rel), "error", "Branch '{branch}' already exists; refusing to reset it".format(
                branch=worktree_branch,
            )))
            continue
        if branch_exists_code not in (0, 1):
            all_ok = False
            summary.append((str(repo_rel), "error", branch_exists_err.strip() or "failed checking branch state"))
            continue

        # The same branch cannot be checked out in multiple worktrees, so each
        # group gets its own synthetic branch name derived from main.
        returncode, _, stderr = run_git_command(
            canonical_repo,
            ["git", "worktree", "add", "-b", worktree_branch, str(target_repo), "main"],
            show_output=False,
        )
        if returncode != 0:
            all_ok = False
            summary.append((str(repo_rel), "error", stderr.strip() or "git worktree add failed"))
            continue

        upstream_code, _, upstream_err = run_git_command(
            target_repo,
            ["git", "branch", "--set-upstream-to", "origin/main", worktree_branch],
            show_output=False,
        )
        if upstream_code != 0:
            all_ok = False
            summary.append((str(repo_rel), "error", upstream_err.strip() or "failed to set upstream"))
            continue

        pull_code, _, pull_err = run_git_command(
            target_repo,
            ["git", "pull", "--ff-only"],
            show_output=False,
        )
        if pull_code != 0:
            all_ok = False
            summary.append((str(repo_rel), "error", pull_err.strip() or "git pull failed"))
            continue

        copied_count, copy_errors = copy_gitignored_files(config, canonical_repo, target_repo)
        copy_note = ", copied {count} allowlisted local config file(s)".format(count=copied_count)
        if copy_errors:
            copy_note += " (with {count} copy error(s): {details})".format(
                count=len(copy_errors),
                details=" | ".join(copy_errors[:3]),
            )

        summary.append(
            (
                str(repo_rel),
                "ok",
                "Created from main on '{branch}' and pulled latest{note}".format(
                    branch=worktree_branch,
                    note=copy_note,
                ),
            )
        )

    print(
        "{orange}→ Recreating shared-lib symlinks...{reset}".format(
            orange=ORANGE,
            reset=RESET,
        ),
        flush=True,
    )
    symlink_summary = recreate_group_shared_lib_symlinks(config, group_root)
    for label, status, message in symlink_summary:
        if status != "ok":
            all_ok = False
        summary.append((label, status, message))

    print("\n" + "~" * 60)
    print("  {orange}SUMMARY{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    for repo_rel, status, message in summary:
        if status == "ok":
            print("  {green}✓ {repo}{reset}: {message}".format(
                green=GREEN,
                repo=repo_rel,
                reset=RESET,
                message=message,
            ))
        else:
            print("  {red}✗ {repo}{reset}: {message}".format(
                red=RED,
                repo=repo_rel,
                reset=RESET,
                message=message,
            ))

    if all_ok:
        print("\n{green}✓ Worktree group '{group}' created successfully{reset}".format(
            green=GREEN,
            group=group_name,
            reset=RESET,
        ))
        print("{yellow}⚠️  Reminder:{reset} this only creates the repos and local files.".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        print("   After you switch to '{group}', use the worktrees menu to initialise".format(
            group=group_name,
        ))
        print("   the stack, then use option 5's worktree database bootstrap command.")
    else:
        print("\n{yellow}⚠️  Group creation finished with errors. Review summary above.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))

    wait_for_key()


def _select_worktree_group(
    config: AppConfig,
    state: AppState,
    prompt: str,
    include_main: bool = True,
) -> Tuple[bool, str]:
    """Select a worktree group using the existing single-key menu UX."""
    groups, _ = discover_worktree_groups(config)
    selectable = groups if include_main else [
        group for group in groups if group != config.main_worktree_group
    ]

    if not selectable:
        print("{yellow}No selectable worktree groups available.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        wait_for_key()
        return False, ""

    if len(selectable) > 9:
        print("{yellow}Too many groups for single-key menu. Keep 9 or fewer groups.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        wait_for_key()
        return False, ""

    print()
    for i, group in enumerate(selectable, 1):
        marker = " (active)" if group == state.active_worktree_group else ""
        print("  {index}. {group}{marker}".format(index=i, group=group, marker=marker))

    print("\nPress number to select, q or Esc to cancel")

    while True:
        print("\n{prompt} (1-{count}, q, Esc): ".format(prompt=prompt, count=len(selectable)), end="", flush=True)
        choice = get_single_char()
        print()

        if choice in ("q", "Q", "\x1b"):
            return False, ""

        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(selectable):
                return True, selectable[index - 1]

        print("{red}✗ Invalid choice.{reset}".format(red=RED, reset=RESET))


def option_worktrees_switch_group(config: AppConfig, state: AppState) -> None:
    """Switch the active worktree group."""
    clear_screen()
    print("~" * 60)
    print("  {orange}SWITCH WORKTREE GROUP{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)

    selected, target_group = _select_worktree_group(config, state, "Select group", include_main=True)
    if not selected:
        return

    if target_group == state.active_worktree_group:
        print("\n{yellow}⚠️  '{group}' is already active.{reset}".format(
            yellow=YELLOW,
            group=target_group,
            reset=RESET,
        ))
        wait_for_key()
        return

    is_valid, reason = validate_worktree_group(config, target_group)
    if not is_valid:
        print("\n{red}✗ Cannot switch: {reason}{reset}".format(red=RED, reason=reason, reset=RESET))
        wait_for_key()
        return

    print(
        "\n{orange}→ Validating and switching to '{group}'...{reset}".format(
            orange=ORANGE,
            group=target_group,
            reset=RESET,
        ),
        flush=True,
    )
    warnings = set_active_worktree_group(config, state, target_group)
    print("\n{green}✓ Active worktree group is now '{group}'{reset}".format(
        green=GREEN,
        group=target_group,
        reset=RESET,
    ))
    if warnings:
        print("\n{yellow}Warnings:{reset}".format(yellow=YELLOW, reset=RESET))
        for warning in warnings:
            print("  {yellow}• {warning}{reset}".format(
                yellow=YELLOW,
                warning=warning,
                reset=RESET,
            ))

    wait_for_key()


def option_worktrees_initialise_active_group(config: AppConfig, state: AppState) -> None:
    """Run the worktree-safe init flow for the currently active non-main group."""
    clear_screen()
    print("~" * 60)
    print("  {orange}INITIALISE ACTIVE WORKTREE{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print()

    active_group = state.active_worktree_group
    if active_group == config.main_worktree_group:
        print("{yellow}⚠️  The main group should keep using option 5's normal make init flow.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        wait_for_key()
        return

    is_valid, reason = validate_worktree_group(config, active_group)
    if not is_valid:
        print("{red}✗ Cannot initialise '{group}': {reason}{reset}".format(
            red=RED,
            group=active_group,
            reason=reason,
            reset=RESET,
        ))
        wait_for_key()
        return

    print("Active group: {orange}{group}{reset}".format(orange=ORANGE, group=active_group, reset=RESET))
    print()
    print("This runs the worktree-safe equivalent of make init:")
    print("  - build containers")
    print("  - install node modules")
    print("  - start the worktree stack")
    print("  - refresh API Composer dependencies")
    print("  - fix API storage permissions")
    print()
    print("{yellow}It does not run migrations or seed the database.{reset}".format(
        yellow=YELLOW,
        reset=RESET,
    ))
    print("Use option 5's worktree database bootstrap command after this finishes.")

    if input("\nRun this initialisation now? (y/n): ").lower() != "y":
        print("\n{red}✗ Aborted.{reset}".format(red=RED, reset=RESET))
        wait_for_key()
        return

    ok, messages = initialise_worktree_group_stack(config, active_group)
    print("\n" + "~" * 60)
    if ok:
        print("{green}✓ Worktree '{group}' initialised successfully.{reset}".format(
            green=GREEN,
            group=active_group,
            reset=RESET,
        ))
        print("{yellow}⚠️  Next step:{reset} use option 5 to run the worktree database bootstrap command.".format(
            yellow=YELLOW,
            reset=RESET,
        ))
    else:
        print("{red}✗ Worktree initialisation failed.{reset}".format(red=RED, reset=RESET))

    if messages:
        print()
        for message in messages:
            colour = YELLOW if ok else RED
            bullet = "•"
            print("  {colour}{bullet} {message}{reset}".format(
                colour=colour,
                bullet=bullet,
                message=message,
                reset=RESET,
            ))

    wait_for_key()


def option_worktrees_delete_group(config: AppConfig, state: AppState) -> None:
    """Delete a non-main worktree group with confirmation."""
    clear_screen()
    print("~" * 60)
    print("  {orange}DELETE WORKTREE GROUP{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)

    selected, group_name = _select_worktree_group(config, state, "Delete group", include_main=False)
    if not selected:
        return

    if group_name == config.main_worktree_group:
        print("\n{red}✗ The main worktree group cannot be deleted.{reset}".format(red=RED, reset=RESET))
        wait_for_key()
        return

    print("\n{red}WARNING: This will remove all worktree folders in '{group}'.{reset}".format(
        red=RED,
        group=group_name,
        reset=RESET,
    ))
    confirmation = input("Type '{group}' to confirm deletion: ".format(group=group_name)).strip()
    if confirmation != group_name:
        print("\n{yellow}⚠️  Confirmation did not match. Aborted.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        wait_for_key()
        return

    is_active_group = group_name == state.active_worktree_group
    if is_active_group:
        ok, message = run_docker_stack_down(
            config,
            state.active_worktree_group,
            config.parent_repo_path_for_group(state.active_worktree_group),
        )
        if not ok:
            print("\n{yellow}⚠️  Docker down warning: {message}{reset}".format(
                yellow=YELLOW,
                message=message,
                reset=RESET,
            ))

    errors = []
    group_root = config.root_path / group_name
    if group_root.is_symlink():
        print("\n{red}✗ Refusing to delete symlinked group folder: {path}{reset}".format(
            red=RED,
            path=group_root,
            reset=RESET,
        ))
        wait_for_key()
        return

    for repo_rel in config.repo_relative_paths:
        canonical_repo = (config.root_path / repo_rel).resolve()
        target_repo = (group_root / repo_rel).resolve()

        if not target_repo.exists():
            continue

        returncode, _, stderr = run_git_command(
            canonical_repo,
            ["git", "worktree", "remove", str(target_repo)],
            show_output=False,
        )
        if returncode != 0:
            err = stderr.strip() or "git worktree remove failed"
            print("\n{yellow}⚠️  Could not remove {repo}: {err}{reset}".format(
                yellow=YELLOW,
                repo=repo_rel,
                err=err,
                reset=RESET,
            ))
            print("Try force remove this worktree? (y/n): ", end="", flush=True)
            force_choice = get_single_char().lower()
            print(force_choice)
            if force_choice == "y":
                force_code, _, force_err = run_git_command(
                    canonical_repo,
                    ["git", "worktree", "remove", "--force", str(target_repo)],
                    show_output=False,
                )
                if force_code != 0:
                    errors.append("{repo}: {err}".format(
                        repo=repo_rel,
                        err=force_err.strip() or "force remove failed",
                    ))
            else:
                errors.append("{repo}: removal skipped".format(repo=repo_rel))

    if errors:
        if is_active_group:
            ok, message = reset_active_group_to_main(config, state)
            if not ok:
                errors.append("failed resetting active group to main: {message}".format(message=message))
        print("\n{red}✗ Group was not fully deleted:{reset}".format(red=RED, reset=RESET))
        for err in errors:
            print("  {red}• {err}{reset}".format(red=RED, err=err, reset=RESET))
        wait_for_key()
        return

    if group_root.exists():
        try:
            shutil.rmtree(group_root)
        except Exception as exc:
            print("\n{yellow}⚠️  Group worktrees removed, but folder cleanup failed: {error}{reset}".format(
                yellow=YELLOW,
                error=exc,
                reset=RESET,
            ))

    if is_active_group:
        ok, message = reset_active_group_to_main(config, state)
        if not ok:
            print("\n{yellow}⚠️  Docker up warning after reset to main: {message}{reset}".format(
                yellow=YELLOW,
                message=message,
                reset=RESET,
            ))

    print("\n{green}✓ Deleted worktree group '{group}'{reset}".format(
        green=GREEN,
        group=group_name,
        reset=RESET,
    ))
    wait_for_key()


def option_worktrees_cleanup_group(config: AppConfig, state: AppState) -> None:
    """Clean up problematic or orphaned worktrees for a non-main group."""
    clear_screen()
    print("~" * 60)
    print("  {orange}CLEANUP WORKTREE GROUP{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    print()
    print("Use this when a worktree group folder was deleted manually,")
    print("or when git still shows stale worktree entries for that group.")
    print()

    group_name = input("Group name to cleanup (not main): ").strip()
    if group_name in config.reserved_worktree_group_names:
        print("\n{red}✗ Cleanup is not allowed for '{group}'.{reset}".format(
            red=RED,
            group=group_name,
            reset=RESET,
        ))
        wait_for_key()
        return

    is_valid, reason = validate_worktree_group_name(config, group_name)
    if not is_valid:
        print("\n{red}✗ Invalid group name: {reason}{reset}".format(
            red=RED,
            reason=reason,
            reset=RESET,
        ))
        wait_for_key()
        return

    if group_name == state.active_worktree_group:
        print("\n{yellow}⚠️  '{group}' is currently active. Switch groups first.{reset}".format(
            yellow=YELLOW,
            group=group_name,
            reset=RESET,
        ))
        wait_for_key()
        return

    print("\n{yellow}This will only target worktrees under: {path}{reset}".format(
        yellow=YELLOW,
        path=config.root_path / group_name,
        reset=RESET,
    ))
    confirmation = input("Type '{group}' to confirm cleanup: ".format(group=group_name)).strip()
    if confirmation != group_name:
        print("\n{yellow}⚠️  Confirmation did not match. Aborted.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
        wait_for_key()
        return

    raw_group_root = config.root_path / group_name
    if raw_group_root.is_symlink():
        print("\n{red}✗ Refusing to clean up symlinked group folder: {path}{reset}".format(
            red=RED,
            path=raw_group_root,
            reset=RESET,
        ))
        wait_for_key()
        return

    group_root = raw_group_root.resolve()
    group_branch = get_worktree_branch_name(config, group_name)
    summary = []

    for repo_rel in config.repo_relative_paths:
        canonical_repo = (config.root_path / repo_rel).resolve()
        repo_label = str(repo_rel)

        if not canonical_repo.exists() or not (canonical_repo / ".git").exists():
            summary.append((repo_label, "error", "Canonical repo missing or invalid"))
            continue

        ok, worktree_paths, err = get_worktree_paths_for_repo(canonical_repo)
        if not ok:
            summary.append((repo_label, "error", err or "Failed to list worktrees"))
            continue

        removed_count = 0
        stale_matches = 0
        repaired_broken_folders = 0
        issues = []
        branch_note = ""

        for worktree_path in sorted(worktree_paths):
            try:
                worktree_path.relative_to(group_root)
            except ValueError:
                continue

            if not worktree_path.exists():
                stale_matches += 1
                continue

            # If the folder exists but the .git file is gone, remove the broken
            # directory directly and let git prune its metadata afterwards.
            if not (worktree_path / ".git").exists():
                try:
                    shutil.rmtree(worktree_path)
                    repaired_broken_folders += 1
                    stale_matches += 1
                except Exception as exc:
                    issues.append("Failed removing broken folder {path}: {error}".format(
                        path=worktree_path,
                        error=exc,
                    ))
                continue

            returncode, _, stderr = run_git_command(
                canonical_repo,
                ["git", "worktree", "remove", "--force", str(worktree_path)],
                show_output=False,
            )
            if returncode == 0:
                removed_count += 1
            else:
                issues.append(stderr.strip() or "Failed removing {path}".format(path=worktree_path))

        prune_code, prune_out, prune_err = run_command_in_dir(
            ["git", "worktree", "prune", "--expire", "now", "--verbose"],
            canonical_repo,
        )
        if prune_code != 0:
            issues.append((prune_err or prune_out or "git worktree prune failed").strip())

        branch_code, _, branch_err = run_git_command(
            canonical_repo,
            ["git", "branch", "-d", group_branch],
            show_output=False,
        )
        if branch_code != 0:
            lowered = (branch_err or "").lower()
            if "not found" not in lowered and "not exist" not in lowered:
                if "not fully merged" in lowered:
                    branch_note = "; preserved branch with unmerged commits: {branch}".format(
                        branch=group_branch,
                    )
                else:
                    issues.append(branch_err.strip() or "Failed deleting branch {branch}".format(branch=group_branch))

        detail = "removed={removed}, repaired-broken={repaired}, stale-matches={stale}, pruned=yes{note}".format(
            removed=removed_count,
            repaired=repaired_broken_folders,
            stale=stale_matches,
            note=branch_note,
        )
        if issues:
            summary.append((repo_label, "error", "{detail}; issues: {issues}".format(
                detail=detail,
                issues=" | ".join(issues),
            )))
        else:
            summary.append((repo_label, "ok", detail))

    print("\n" + "~" * 60)
    print("  {orange}CLEANUP SUMMARY{reset}".format(orange=ORANGE, reset=RESET))
    print("~" * 60)
    had_errors = False
    for repo_label, status, detail in summary:
        if status == "ok":
            print("  {green}✓ {repo}{reset}: {detail}".format(
                green=GREEN,
                repo=repo_label,
                reset=RESET,
                detail=detail,
            ))
        else:
            had_errors = True
            print("  {red}✗ {repo}{reset}: {detail}".format(
                red=RED,
                repo=repo_label,
                reset=RESET,
                detail=detail,
            ))

    if not had_errors and raw_group_root.exists():
        try:
            shutil.rmtree(raw_group_root)
            print("\n{green}✓ Removed group folder: {path}{reset}".format(
                green=GREEN,
                path=raw_group_root,
                reset=RESET,
            ))
        except Exception as exc:
            print("\n{yellow}⚠️  Git metadata cleaned, but could not remove group folder: {error}{reset}".format(
                yellow=YELLOW,
                error=exc,
                reset=RESET,
            ))

    if had_errors:
        print("\n{yellow}⚠️  Cleanup completed with some errors. See details above.{reset}".format(
            yellow=YELLOW,
            reset=RESET,
        ))
    else:
        print("\n{green}✓ Cleanup complete for worktree group '{group}'.{reset}".format(
            green=GREEN,
            group=group_name,
            reset=RESET,
        ))

    wait_for_key()


def option_w_worktrees(config: AppConfig, state: AppState) -> None:
    """Show the worktrees submenu and dispatch its actions."""
    while True:
        clear_screen()
        print("~" * 60)
        print("  {orange}WORKTREES{reset}".format(orange=ORANGE, reset=RESET))
        print("~" * 60)
        print()
        print("  1. List worktree groups")
        print("  2. Create a worktree group")
        print("  3. Switch worktree group")
        print("  4. Delete a worktree group")
        print("  5. Help")
        print("  6. Cleanup problematic worktrees")
        print("  7. Initialise active worktree")
        print("\nPress q or Esc to return")
        print("\n" + "~" * 60)

        print("\nSelect option (1-7, q, Esc): ", end="", flush=True)
        choice = get_single_char()
        print()

        if choice in ("q", "Q", "\x1b"):
            return
        if choice == "1":
            option_worktrees_list_groups(config, state)
        elif choice == "2":
            option_worktrees_create_group(config, state)
        elif choice == "3":
            option_worktrees_switch_group(config, state)
        elif choice == "4":
            option_worktrees_delete_group(config, state)
        elif choice == "5":
            show_worktrees_help(config)
        elif choice == "6":
            option_worktrees_cleanup_group(config, state)
        elif choice == "7":
            option_worktrees_initialise_active_group(config, state)
        else:
            print("\n{red}✗ Invalid option. Please select 1-7.{reset}".format(red=RED, reset=RESET))
            wait_for_key()
