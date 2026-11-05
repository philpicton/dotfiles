#!/usr/bin/env node
// PreToolUse hook for Bash: gates git commands that modify a repository,
// according to the user's git mode (see ./git-mode.mjs):
//   readonly  deny them (default; also used if the flag file is missing/invalid)
//   ask       prompt the user to approve each one
//   allow     let local ones through; remote ones (push/pull/fetch/clone) still prompt
// Read-only git commands are never affected.
//
import { readGitMode, GIT_MODE_FILE } from "./git-mode.mjs";

// Subcommands that talk to a remote. These always need approval unless denied.
const REMOTE_SUBCOMMANDS = new Set(["push", "pull", "fetch", "clone"]);

const DENIED_SUBCOMMANDS = new Set([
  "add",
  "commit",
  "push",
  "pull",
  "checkout",
  "switch",
  "merge",
  "rebase",
  "reset",
  "revert",
  "stash",
  "fetch",
  "clone",
  "clean",
  "rm",
  "mv",
  "cherry-pick",
  "bisect",
  "worktree",
  "submodule",
  "filter-branch",
  "gc",
  "prune",
  "replace",
  "notes",
]);

const READONLY_BRANCH_FLAGS = new Set([
  "-a",
  "-r",
  "--all",
  "--remotes",
  "--show-current",
  "-v",
  "-vv",
  "--list",
  "-l",
]);

// Global git options that take a separate value argument.
const GLOBAL_OPTS_WITH_VALUE = new Set([
  "-C",
  "-c",
  "--git-dir",
  "--work-tree",
  "--namespace",
]);

function tokenize(segment) {
  const tokens = [];
  const re = /"((?:\\.|[^"\\])*)"|'([^']*)'|(\S+)/g;
  let m;
  while ((m = re.exec(segment))) tokens.push(m[1] ?? m[2] ?? m[3]);
  return tokens;
}

function gitArgs(tokens) {
  let i = 0;
  // Skip env assignments and simple wrappers (FOO=1 sudo command git ...).
  while (
    i < tokens.length &&
    (/^[A-Za-z_][A-Za-z0-9_]*=/.test(tokens[i]) ||
      ["sudo", "command", "env", "exec"].includes(tokens[i]))
  )
    i++;
  if (!/(^|\/)git$/.test(tokens[i] ?? "")) return null;
  i++;
  while (i < tokens.length && tokens[i].startsWith("-")) {
    if (GLOBAL_OPTS_WITH_VALUE.has(tokens[i])) i++;
    i++;
  }
  return tokens.slice(i);
}

function violation(args) {
  const [sub, ...rest] = args;
  if (!sub) return null;
  if (DENIED_SUBCOMMANDS.has(sub)) return `git ${sub}`;
  if (sub === "reflog" && ["delete", "expire"].includes(rest[0]))
    return `git reflog ${rest[0]}`;
  if (sub === "branch" && !rest.every((a) => READONLY_BRANCH_FLAGS.has(a)))
    return `git branch ${rest.join(" ")}`;
  if (sub === "tag" && rest.length && !["-l", "--list"].includes(rest[0]))
    return `git tag ${rest.join(" ")}`;
  if (
    sub === "remote" &&
    rest.length &&
    rest[0] !== "-v" &&
    rest[0] !== "get-url"
  )
    return `git remote ${rest.join(" ")}`;
  return null;
}

function decide(decision, reason) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: decision,
        permissionDecisionReason: reason,
      },
    }),
  );
}

let input = "";
process.stdin.on("data", (c) => (input += c));
process.stdin.on("end", () => {
  const command = JSON.parse(input).tool_input?.command ?? "";
  // Split on shell separators, and look inside $(...) / backticks too.
  const segments = command.replace(/\$\(|`|\)/g, "\n").split(/&&|\|\||[;|\n]/);
  const hits = [];
  for (const segment of segments) {
    const args = gitArgs(tokenize(segment.trim()));
    const hit = args && violation(args);
    if (hit) hits.push({ hit, remote: REMOTE_SUBCOMMANDS.has(args[0]) });
  }
  if (!hits.length) return;

  const mode = readGitMode();
  const list = hits.map((h) => `\`${h.hit}\``).join(", ");

  if (mode === "readonly") {
    decide(
      "deny",
      `Blocked by global rules: ${list} modifies the repository and git mode is "readonly" (${GIT_MODE_FILE}). Only read-only git commands are allowed. Do not edit the git mode file; ask the user to run the command themselves or to change the git mode to "ask" or "allow".`,
    );
  } else if (mode === "ask") {
    decide(
      "ask",
      `Git mode is "ask": ${list} modifies the repository and needs your approval.`,
    );
  } else {
    // "allow": local changes pass through to the normal permission flow;
    // anything touching a remote still asks.
    const remote = hits.filter((h) => h.remote);
    if (remote.length) {
      decide(
        "ask",
        `Git mode is "allow", but ${remote.map((h) => `\`${h.hit}\``).join(", ")} talks to a remote and always needs your approval.`,
      );
    }
  }
});
