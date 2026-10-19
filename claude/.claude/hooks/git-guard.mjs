#!/usr/bin/env node
// PreToolUse hook for Bash: blocks git commands that modify a repository.
// Mirrors the git section of opencode's permission.bash config, which needs
// "deny `git branch *` but allow `git branch -a`" semantics that plain
// Claude Code permission rules (deny always beats allow) can't express.

const DENIED_SUBCOMMANDS = new Set([
  "add", "commit", "push", "pull", "checkout", "switch", "merge", "rebase",
  "reset", "revert", "stash", "fetch", "clone", "clean", "rm", "mv",
  "cherry-pick", "bisect", "worktree", "submodule", "filter-branch", "gc",
  "prune", "replace", "notes",
]);

const READONLY_BRANCH_FLAGS = new Set([
  "-a", "-r", "--all", "--remotes", "--show-current", "-v", "-vv", "--list", "-l",
]);

// Global git options that take a separate value argument.
const GLOBAL_OPTS_WITH_VALUE = new Set(["-C", "-c", "--git-dir", "--work-tree", "--namespace"]);

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
    (/^[A-Za-z_][A-Za-z0-9_]*=/.test(tokens[i]) || ["sudo", "command", "env", "exec"].includes(tokens[i]))
  ) i++;
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
  if (sub === "reflog" && ["delete", "expire"].includes(rest[0])) return `git reflog ${rest[0]}`;
  if (sub === "branch" && !rest.every((a) => READONLY_BRANCH_FLAGS.has(a))) return `git branch ${rest.join(" ")}`;
  if (sub === "tag" && rest.length && !["-l", "--list"].includes(rest[0])) return `git tag ${rest.join(" ")}`;
  if (sub === "remote" && rest.length && rest[0] !== "-v" && rest[0] !== "get-url") return `git remote ${rest.join(" ")}`;
  return null;
}

let input = "";
process.stdin.on("data", (c) => (input += c));
process.stdin.on("end", () => {
  const command = JSON.parse(input).tool_input?.command ?? "";
  // Split on shell separators, and look inside $(...) / backticks too.
  const segments = command
    .replace(/\$\(|`|\)/g, "\n")
    .split(/&&|\|\||[;|\n]/);
  for (const segment of segments) {
    const args = gitArgs(tokenize(segment.trim()));
    const hit = args && violation(args);
    if (hit) {
      process.stdout.write(JSON.stringify({
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason: `Blocked by global rules: \`${hit}\` modifies the repository. Only read-only git commands are allowed (see ~/.claude/rules/general-guidelines.md). Ask the user to run it themselves if needed.`,
        },
      }));
      return;
    }
  }
});
