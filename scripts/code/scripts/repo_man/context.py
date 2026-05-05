"""Shared application configuration and runtime state for repo-man."""

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class AppConfig:
    """Store the user-editable configuration and its derived paths."""

    ical_calendar_ids: List[str]
    rootdir: str
    repos: List[str]
    editor_menu_options: List[Dict[str, str]]
    make_commands: List[Dict[str, str]]
    worktree_branch_template: str
    worktree_gitignored_copy_patterns: List[str]
    main_worktree_group: str = "main"
    main_worktree_folder_name: str = "haysto-v2"
    root_path: Path = field(init=False)
    repo_relative_paths: List[Path] = field(init=False)
    repo_paths: List[Path] = field(init=False)
    reserved_worktree_group_names: Set[str] = field(init=False)
    worktree_state_file: Path = field(init=False)

    def __post_init__(self) -> None:
        """Expand the editable constants into the derived paths the app uses."""
        self.ical_calendar_ids = list(self.ical_calendar_ids)
        self.repos = list(self.repos)
        self.editor_menu_options = [dict(option) for option in self.editor_menu_options]
        self.make_commands = [dict(command) for command in self.make_commands]
        self.worktree_gitignored_copy_patterns = list(self.worktree_gitignored_copy_patterns)
        self.root_path = Path(self.rootdir).expanduser().resolve()
        self.repo_relative_paths = [Path(repo) for repo in self.repos]
        self.repo_paths = [(self.root_path / repo).resolve() for repo in self.repo_relative_paths]
        self.reserved_worktree_group_names = {
            self.main_worktree_group,
            self.main_worktree_folder_name,
        }
        # Require a named placeholder so repo-man can derive one synthetic branch
        # per worktree group without hardcoding the branch format in code.
        if "{group}" not in self.worktree_branch_template:
            raise ValueError("worktree_branch_template must contain '{group}'")
        self.worktree_state_file = self.root_path / ".repo-man-worktrees.json"

    def repo_paths_for_group(self, group_name: str) -> List[Path]:
        """Return repository paths for either the canonical repos or a worktree group."""
        if group_name == self.main_worktree_group:
            return list(self.repo_paths)
        group_root = self.root_path / group_name
        return [(group_root / repo).resolve() for repo in self.repo_relative_paths]

    def parent_repo_path_for_group(self, group_name: str) -> Path:
        """Return the parent repo path used for make and docker actions."""
        return self.repo_paths_for_group(group_name)[0]

    def worktree_branch_name(self, group_name: str) -> str:
        """Render the configured synthetic branch name for one worktree group."""
        return self.worktree_branch_template.format(group=group_name)


@dataclass
class AppState:
    """Store mutable runtime state that used to live in module globals."""

    active_worktree_group: str = "main"
    startup_notice: Optional[str] = None
    show_notifications: bool = False
    loading_sentinel: object = field(default_factory=object)
    cache_lock: Any = field(default_factory=threading.Lock)
    cache_ttl: int = 60
    cache: Dict[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        """Initialise the notification cache once the sentinel exists."""
        self.reset_cache()

    def reset_cache(self) -> None:
        """Reset the background dashboard cache to its initial loading state."""
        self.cache = {
            "review_count": self.loading_sentinel,
            "notification_count": self.loading_sentinel,
            "calendar_events": self.loading_sentinel,
            "fetched_at": 0.0,
            "is_fetching": False,
        }
