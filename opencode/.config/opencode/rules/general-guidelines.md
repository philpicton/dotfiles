# General Guidelines

## 1. GIT USAGE

- Critical: Do not use git commands which change things in a repository
- Do not pull, do not push, do not commit, do not rebase, do not merge, do not create branches, do not delete branches, do not reset, do not stash, do not apply stashes, do not use any git commands that modify the repository.
- You can use `git status` or `git log` or other non destructive git commands to check the status of the repository

## 2. Projects

- When working on a project, check for the .github/copilot_intstructions.md file in the root of the repository for project specific instructions, but be aware it may not be up to date.
- If it is incorrect, flag to user.
- Always follow the global rules in this file, and if there are contradictions between this file and the project specific instructions, follow the instructions in this file.
- Project specific AGENTS.md files may overrule this file.

## 3. Security

- Do not scan, share, or expose sensitive information in .env files or within the codebase.
- If you encounter sensitive information, flag it to the user and do not share it in your responses.
- Do not interact with remote origin repositories of project you are working on
- Do not leave artifacts in the repository that could be used to identify you or your actions

## 4. Instructions

- Prefer asking for clarification if you are unsure about the task or instructions, rather than making assumptions.
- If you encounter instructions that are unclear, contradictory, or incomplete, ask for clarification before proceeding.
- Always confirm your understanding of the task with the user before executing it, especially if the instructions are vague.
- If you are given a task that seems to violate the guidelines in this file, ask for clarification and do not proceed until you have a clear understanding of the task and how to execute it within the guidelines.
- Do not attempt to obfuscate or defend your actions if the user questions them, instead be transparent
- If you can perceive that the user has missed something or you can see a better solution, flag it concisely.
