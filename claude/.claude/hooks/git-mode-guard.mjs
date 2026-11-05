#!/usr/bin/env node
// PreToolUse hook for Bash and the file-editing tools: stops Claude from
// changing the git mode flag file (~/.claude/git-mode and its dotfiles source).
// The mode is the user's switch; only they may edit it.

import { realpathSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";

const FILE_NAME = "git-mode";
// `git-mode` as a standalone name: not `git-mode-guard.mjs` or `git-mode.mjs`.
const MENTION = /(^|[^\w.-])git-mode(?![\w.-])/;
// Commands that only read; any segment mentioning the file must start with one.
const READ_ONLY = new Set([
  "cat",
  "head",
  "tail",
  "less",
  "bat",
  "ls",
  "stat",
  "readlink",
  "realpath",
  "file",
  "wc",
  "grep",
  "rg",
  "diff",
]);

function realDir(path) {
  try {
    return realpathSync(path);
  } catch {
    return path;
  }
}

// True for <any .claude dir>/git-mode, following symlinks on the directory
// (covers ~/.claude/git-mode and ~/.dotfiles/claude/.claude/git-mode).
function isFlagFile(filePath, cwd) {
  const full = resolve(cwd ?? process.cwd(), filePath);
  return (
    basename(full) === FILE_NAME &&
    basename(realDir(dirname(full))) === ".claude"
  );
}

function bashTouchesFlag(command) {
  if (!MENTION.test(command)) return false;
  // Redirection could write to it (`echo allow > ~/.claude/git-mode`).
  if (command.includes(">")) return true;
  const segments = command.replace(/\$\(|`|\)/g, "\n").split(/&&|\|\||[;|\n]/);
  return segments.some((segment) => {
    if (!MENTION.test(segment)) return false;
    const first = segment.trim().split(/\s+/)[0];
    return !READ_ONLY.has(first);
  });
}

let input = "";
process.stdin.on("data", (c) => (input += c));
process.stdin.on("end", () => {
  const { tool_name: tool, tool_input: args = {}, cwd } = JSON.parse(input);
  const blocked =
    tool === "Bash"
      ? bashTouchesFlag(args.command ?? "")
      : [args.file_path, args.notebook_path].some(
          (p) => p && isFlagFile(p, cwd),
        );
  if (!blocked) return;
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason:
          "Blocked by global rules: the git mode file (~/.claude/git-mode) is the user's switch and Claude must never create, edit, move or delete it. If a git command is blocked, ask the user to change the mode themselves.",
      },
    }),
  );
});
