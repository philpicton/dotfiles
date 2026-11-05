// Shared helper for the git hooks: reads the user's git mode flag file.
//
// ~/.claude/git-mode is a stow symlink to ~/.dotfiles/claude/.claude/git-mode.
// It must contain exactly one of the values below (surrounding whitespace is
// ignored). A missing, unreadable or malformed file falls back to "readonly".
// It is read on every hook call, so changes take effect immediately.

import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

export const GIT_MODE_FILE = join(homedir(), ".claude", "git-mode");
export const GIT_MODES = ["readonly", "ask", "allow"];
export const DEFAULT_GIT_MODE = "readonly";

export function readGitMode() {
  try {
    const value = readFileSync(GIT_MODE_FILE, "utf8").trim();
    return GIT_MODES.includes(value) ? value : DEFAULT_GIT_MODE;
  } catch {
    return DEFAULT_GIT_MODE;
  }
}
