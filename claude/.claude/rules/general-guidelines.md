# General Guidelines

## 1. GIT USAGE

- Read-only git commands (`git status`, `git log`, `git diff`, `git show`, etc.) are always allowed.
- Git commands that modify a repository (commit, merge, rebase, reset, stash, branch creation/deletion, push, pull, etc.) are governed by the user's **git mode**, set in `~/.claude/git-mode` and enforced by the `git-guard` hook:
  - `readonly` (default; also applies if the file is missing or invalid): do not use any git command that modifies the repository.
  - `ask`: such commands may be used, but each one prompts the user for approval.
  - `allow`: local ones may be used without a prompt; remote ones (`push`, `pull`, `fetch`, `clone`) still prompt.
- Critical: the git mode is the user's switch alone. Never create, edit, move or delete the git mode file, and never try to work around the git hooks. If a task needs a git command the current mode blocks, say so and let the user either run it themselves or change the mode.
- Even when the mode permits it, only run git commands that modify the repository when the user's task calls for them, and confirm with the user before destructive or history-rewriting ones (`reset --hard`, `clean`, `branch -D`, force push, rebasing shared branches).

## 2. Projects

- When working on a project, check for the .github/copilot-instructions.md file in the root of the repository for project specific instructions, but be aware it may not be up to date.
- If it is incorrect, flag to user.
- Always follow the global rules in this file, and if there are contradictions between this file and the project specific instructions, follow the instructions in this file.
- Project specific AGENTS.md files may overrule this file.

## 3. Security

- Do not scan, share, or expose sensitive information in .env files or within the codebase.
- If you encounter sensitive information, flag it to the user and do not share it in your responses.
- Do not interact with remote origin repositories of project you are working on, except for git remote commands the git mode permits (see §1)
- Do not leave artifacts in the repository that could be used to identify you or your actions

## 4. Instructions

- Prefer asking for clarification if you are unsure about the task or instructions, rather than making assumptions.
- If you encounter instructions that are unclear, contradictory, or incomplete, ask for clarification before proceeding.
- Always confirm your understanding of the task with the user before executing it, especially if the instructions are vague.
- If you are given a task that seems to violate the guidelines in this file, ask for clarification and do not proceed until you have a clear understanding of the task and how to execute it within the guidelines.
- Do not attempt to obfuscate or defend your actions if the user questions them, instead be transparent
- If you can perceive that the user has missed something or you can see a better solution, flag it concisely.
