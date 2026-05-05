"""Terminal UI helpers shared across repo-man modules."""

import datetime
import getpass
import os
import shutil
import sys
import termios
import tty
from typing import List

# ANSI colour codes are shared across most menus, so keeping them in one module
# avoids redefining them in every feature module.
ORANGE = "\033[38;5;208m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
DIM = "\033[2m"
RESET = "\033[0m"


def clear_screen() -> None:
    """Clear the terminal screen."""
    if not sys.stdout.isatty():
        return
    os.system("clear")


def wait_for_key() -> None:
    """Pause until the user presses Enter."""
    if not sys.stdin.isatty():
        return
    try:
        input("\n\nPress Enter to return to menu...")
    except EOFError:
        pass


def get_single_char() -> str:
    """Read one character without waiting for Enter."""
    if not sys.stdin.isatty():
        try:
            return sys.stdin.read(1) or "q"
        except EOFError:
            return "q"

    fd = sys.stdin.fileno()
    try:
        old_settings = termios.tcgetattr(fd)
    except termios.error:
        return "q"
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch or "q"


def get_time_greeting() -> str:
    """Generate a greeting based on the current time of day."""
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

    return "{greeting} {username}".format(greeting=greeting, username=username)


def truncate_value(value: str, width: int) -> str:
    """Truncate a table cell to a fixed width using an ellipsis when needed."""
    text = (value or "-").replace("\n", " ").strip()
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def print_fixed_width_table(headers: List[str], rows: List[List[str]]) -> None:
    """Print a compact aligned table that shrinks to fit the terminal width."""
    terminal_width = shutil.get_terminal_size((140, 24)).columns

    # These caps keep the docker table readable without one wide column
    # pushing everything else off screen.
    max_caps = [30, 32, 24, 38, 20]
    min_caps = [14, 12, 12, 12, 10]

    col_widths = []
    for idx, header in enumerate(headers):
        longest_cell = max(
            (len((row[idx] or "-").replace("\n", " ").strip()) for row in rows),
            default=0,
        )
        width = max(len(header), longest_cell)
        width = min(width, max_caps[idx])
        width = max(width, min_caps[idx])
        col_widths.append(width)

    def current_total() -> int:
        return sum(col_widths) + (3 * (len(col_widths) - 1))

    # Shrink the least important columns first so names and status stay legible.
    shrink_order = [3, 1, 2, 0, 4]
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

    header_line = " | ".join(headers[i].ljust(col_widths[i]) for i in range(len(headers)))
    divider_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print(header_line)
    print(divider_line)

    for row in rows:
        line = " | ".join(
            truncate_value(row[i], col_widths[i]).ljust(col_widths[i])
            for i in range(len(headers))
        )
        print(line)
