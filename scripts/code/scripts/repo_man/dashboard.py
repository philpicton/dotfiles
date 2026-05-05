"""GitHub, calendar, and dashboard cache helpers for the main menu."""

import json
import shutil
import subprocess
import threading
import time
from typing import Any, List, Tuple

from .context import AppConfig, AppState


def get_github_review_requests() -> int:
    """Get the number of GitHub PRs currently requesting the user's review."""
    if shutil.which("gh") is None:
        return -1

    try:
        result = subprocess.run(
            ["gh", "search", "prs", "--review-requested=@me", "--state=open", "--json", "number"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return -1

        prs = json.loads(result.stdout)
        return len(prs)
    except (json.JSONDecodeError, FileNotFoundError, Exception):
        return -1


def get_github_unread_notifications() -> int:
    """Get the number of unread GitHub notifications."""
    if shutil.which("gh") is None:
        return -1

    try:
        result = subprocess.run(
            ["gh", "api", "notifications"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return -1

        notifications = json.loads(result.stdout)
        return len(notifications)
    except (json.JSONDecodeError, FileNotFoundError, Exception):
        return -1


def get_todays_calendar_events(config: AppConfig) -> List[str]:
    """Get today's calendar events using icalBuddy when it is available."""
    if shutil.which("icalBuddy") is None:
        return []

    try:
        result = subprocess.run(
            [
                "icalBuddy",
                "-b",
                "• ",
                "-iep",
                "title,datetime",
                "-n",
                "-nc",
                "-ic",
                ",".join(config.ical_calendar_ids),
                "eventsToday",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return []

        output = result.stdout.strip()
        if not output or "No items." in output:
            return []

        return [line for line in output.splitlines() if line.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return []


def run_cache_fetch(config: AppConfig, state: AppState) -> None:
    """Fetch all dashboard values concurrently and write them into shared state."""
    with state.cache_lock:
        if state.cache["is_fetching"]:
            return
        state.cache["is_fetching"] = True

    results = {}

    def _reviews() -> None:
        results["review_count"] = get_github_review_requests()

    def _notifications() -> None:
        results["notification_count"] = get_github_unread_notifications()

    def _calendar() -> None:
        results["calendar_events"] = get_todays_calendar_events(config)

    try:
        threads = [
            threading.Thread(target=_reviews, daemon=True),
            threading.Thread(target=_notifications, daemon=True),
            threading.Thread(target=_calendar, daemon=True),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        with state.cache_lock:
            state.cache.update(results)
            state.cache["fetched_at"] = time.monotonic()
    finally:
        with state.cache_lock:
            state.cache["is_fetching"] = False


def refresh_cache_in_background(config: AppConfig, state: AppState, force: bool = False) -> None:
    """Refresh the dashboard cache in the background when it is stale."""
    with state.cache_lock:
        age = time.monotonic() - state.cache["fetched_at"]
        if not force and state.cache["fetched_at"] > 0 and age < state.cache_ttl:
            return
        if state.cache["is_fetching"]:
            return

    threading.Thread(target=run_cache_fetch, args=(config, state), daemon=True).start()


def get_cache_snapshot(state: AppState) -> Tuple[Any, Any, Any]:
    """Return a stable snapshot of the cached dashboard values for menu rendering."""
    with state.cache_lock:
        return (
            state.cache["review_count"],
            state.cache["notification_count"],
            state.cache["calendar_events"],
        )
