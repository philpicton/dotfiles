#!/usr/bin/env python3
"""
REPO MAN
Haya Repositories Manager - TUI for managing git repositories

"""

from repo_man import run_app
from repo_man.context import AppConfig, AppState

# CUSTOMISE THE BELOW VALUES ------------------------------------------------

# Calendar UUIDs to include in the notifications panel.
# Add multiple UUIDs as separate strings in the list.
# Find yours by running: icalBuddy calendars
ICAL_CALENDAR_IDS = [
    "abc1234",
]

# The folder where you store your repos, and any new worktrees created by this script.
# Customise this to your preferred location.
ROOTDIR = "~/code/haya"

# Main repository folder names relative to the ROOTDIR.
# haysto-v2 must be first, and be found at ROOTDIR/haysto-v2 for the script to work correctly.
# Add any others you want to manage at the end.
REPOS = [
    "haysto-v2",
    "haysto-v2/haysto-v2-api",
    "haysto-v2/haysto-v2-collaborate",
    "haysto-v2/haysto-v2-collect",
    "haysto-v2/haysto-v2-create",
    "haysto-v2/haysto-v2-dev",
    "haysto-v2/lib/js/haysto-v2-lib_shared",
    "enquiry-form",
]

# You can add other cli commands here, use letters if you run out of numbers!
MAKE_COMMANDS = [
    {"key": "1", "label": "Restart docker containers, manage node modules", "command": "make restart"},
    {"key": "2", "label": "Rebuild containers and app", "command": "make init"},
    {"key": "3", "label": "Containers down", "command": "make down"},
    {"key": "4", "label": "Artisan migrate", "command": "docker compose exec haysto-api php artisan migrate"},
    {"key": "5", "label": "Update permissions", "command": "make update_permissions"},
    {"key": "6", "label": "Bulk seed cases", "command": "make cases"},
    {"key": "7", "label": "Seed a case at a particular stage", "command": "make case"},
    {"key": "8", "label": "Shell into haysto-v2-api container", "command": "docker compose exec haysto-api bash"},
] # ---------------------------------------------------------------------------

# Synthetic branch name used when creating one branch per worktree group.
# Repo-man replaces {group} with the group name you enter.
WORKTREE_BRANCH_TEMPLATE = "worktree-{group}/main"

# Gitignored files to copy into a new worktree group.
# Keep this allowlist small and focused on local config you genuinely want to
# carry across, such as .env files. Dependencies and generated assets should be
# installed or rebuilt inside the new worktree instead of being copied.
WORKTREE_GITIGNORED_COPY_PATTERNS = [
    ".env",
    ".env.*",
    "docker/nginx/certificates/certificate.*",
]

def build_app_config() -> AppConfig:
    """Build the shared application config from the editable constants above."""
    return AppConfig(
        ical_calendar_ids=ICAL_CALENDAR_IDS,
        rootdir=ROOTDIR,
        repos=REPOS,
        make_commands=MAKE_COMMANDS,
        worktree_branch_template=WORKTREE_BRANCH_TEMPLATE,
        worktree_gitignored_copy_patterns=WORKTREE_GITIGNORED_COPY_PATTERNS,
    )


def main() -> None:
    """Build config and runtime state, then launch the TUI."""
    config = build_app_config()
    state = AppState(active_worktree_group=config.main_worktree_group)
    run_app(config, state)


if __name__ == "__main__":
    main()
