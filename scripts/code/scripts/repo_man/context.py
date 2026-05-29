"""Shared application configuration and runtime state for repo-man."""

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class AppConfig:
    """Store the user-editable configuration and its derived paths."""

    ical_calendar_ids: List[str]
    rootdir: str
    repos: List[str]
    make_commands: List[Dict[str, str]]
    root_path: Path = field(init=False)
    repo_paths: List[Path] = field(init=False)

    def __post_init__(self) -> None:
        """Expand the editable constants into the derived paths the app uses."""
        self.ical_calendar_ids = list(self.ical_calendar_ids)
        self.repos = list(self.repos)
        self.make_commands = [dict(command) for command in self.make_commands]
        self.root_path = Path(self.rootdir).expanduser().resolve()
        self.repo_paths = [(self.root_path / Path(repo)).resolve() for repo in self.repos]

    def parent_repo_path(self) -> Path:
        """Return the main Haysto repository path used for make commands."""
        return self.repo_paths[0]


@dataclass
class AppState:
    """Store mutable runtime state that used to live in module globals."""

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
