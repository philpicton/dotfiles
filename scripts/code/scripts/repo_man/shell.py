"""Subprocess, Git, fzf, and editor-launch helper functions."""

import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple


EditorLauncher = Callable[[Path], Tuple[int, str]]


def run_git_command(
    repo_path: Path,
    command: List[str],
    show_output: bool = True,
) -> Tuple[int, str, str]:
    """Run a git command in a specific repository."""
    try:
        if show_output:
            # Use Popen here so commands can stream their output to the TUI.
            process = subprocess.Popen(
                command,
                cwd=repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate()
            if stdout:
                print(stdout, end="")
            if stderr:
                print(stderr, end="", file=sys.stderr)
            return process.returncode, stdout, stderr

        result = subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as exc:
        return 1, "", str(exc)


def run_command(command: List[str]) -> Tuple[int, str, str]:
    """Run a shell command and capture stdout and stderr."""
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as exc:
        return 1, "", str(exc)


def run_command_in_dir(command: List[str], cwd: Path) -> Tuple[int, str, str]:
    """Run a command in a specific directory and capture stdout and stderr."""
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as exc:
        return 1, "", str(exc)


def normalize_branch_selection(selected_branch: str) -> str:
    """Normalize `git branch --all` output into a branch name."""
    branch = selected_branch.strip()

    if branch.startswith("* "):
        branch = branch[2:].strip()

    # Match the original shell helper behaviour by keeping the final token.
    if " " in branch:
        branch = branch.split()[-1]

    if branch.startswith("remotes/"):
        parts = branch.split("/", 2)
        if len(parts) == 3:
            branch = parts[2]

    return branch


def pick_source_branch_with_fzf(repo_path: Path, current_branch: str) -> Tuple[bool, str]:
    """Open fzf with the current branch pre-filled as the query."""
    returncode, branches, stderr = run_git_command(
        repo_path,
        ["git", "branch", "--all"],
        show_output=False,
    )

    if returncode != 0:
        raise RuntimeError(stderr.strip() or "Failed to list branches")

    branch_lines = [line for line in branches.splitlines() if "HEAD" not in line]
    if not branch_lines:
        raise RuntimeError("No branches available")

    try:
        fzf_result = subprocess.run(
            [
                "fzf",
                "--height",
                "40%",
                "--reverse",
                "--prompt",
                "{name}> ".format(name=repo_path.name),
                "--header",
                "Select source branch (current branch pre-selected, Esc to skip)",
                "--bind",
                "esc:abort",
                "--query",
                current_branch,
            ],
            input="\n".join(branch_lines),
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("fzf not found. Please install fzf to use this option.") from exc

    if fzf_result.returncode != 0:
        return False, ""

    selected_line = fzf_result.stdout.strip()
    if not selected_line:
        return False, ""

    branch_name = normalize_branch_selection(selected_line)
    if not branch_name:
        return False, ""

    return True, branch_name


def input_with_default(prompt: str, default: str) -> str:
    """Prompt for text input with a pre-populated default value."""
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
    """Open fzf to select a branch, treating Esc as a skip."""
    returncode, branches, stderr = run_git_command(
        repo_path,
        ["git", "branch", "--all"],
        show_output=False,
    )

    if returncode != 0:
        raise RuntimeError(stderr.strip() or "Failed to list branches")

    branch_lines = [line for line in branches.splitlines() if "HEAD" not in line]
    if not branch_lines:
        raise RuntimeError("No branches available")

    try:
        fzf_result = subprocess.run(
            [
                "fzf",
                "--height",
                "40%",
                "--reverse",
                "--prompt",
                "{name}> ".format(name=repo_path.name),
                "--header",
                "Select branch (Esc to keep current branch)",
                "--bind",
                "esc:abort",
            ],
            input="\n".join(branch_lines),
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("fzf not found. Please install fzf to use this option.") from exc

    if fzf_result.returncode != 0:
        return False, ""

    selected_line = fzf_result.stdout.strip()
    if not selected_line:
        return False, ""

    branch_name = normalize_branch_selection(selected_line)
    if not branch_name:
        return False, ""

    return True, branch_name


def run_editor_command(command: List[str], success_message: str) -> Tuple[int, str]:
    """Run an editor command and return the exit code plus message."""
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            error_message = (result.stderr or result.stdout or "").strip()
            return result.returncode, error_message
        return 0, success_message
    except FileNotFoundError as exc:
        return 1, "Required command not found: {error}".format(error=exc)
    except Exception as exc:
        return 1, str(exc)


def open_repo_in_kitty_tab(repo_path: Path) -> Tuple[int, str]:
    """Open the repository in nvim in a new kitty tab."""
    cmd = [
        "kitty",
        "@",
        "launch",
        "--type=tab",
        "--cwd={path}".format(path=repo_path),
        "--tab-title= {name}".format(name=repo_path.name),
        "--copy-env",
        "--dont-take-focus",
        "--add-to-session",
        "!",
        "nvim",
    ]
    return run_editor_command(cmd, "Opened in new kitty tab")


def open_repo_in_vscode(repo_path: Path) -> Tuple[int, str]:
    """Open the repository in VS Code."""
    return run_editor_command(["code", str(repo_path)], "Opened in VS Code")


def open_repo_in_zed(repo_path: Path) -> Tuple[int, str]:
    """Open the repository in Zed."""
    return run_editor_command(["zed", str(repo_path)], "Opened in Zed")


def get_editor_launcher(function_name: str) -> Optional[EditorLauncher]:
    """Resolve a configured editor launcher directly from this module.

    EDITOR_MENU_OPTIONS already stores the function name, so keep that config as
    the single source of truth and only allow lookups that follow the editor
    launcher naming convention.
    """
    launcher_name = function_name.strip()
    if not launcher_name.startswith("open_repo_in_"):
        return None

    launcher = getattr(sys.modules[__name__], launcher_name, None)
    if not callable(launcher):
        return None
    return launcher
