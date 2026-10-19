#!/usr/bin/env node
// PreToolUse hook for Bash: blocks shell commands that reference a .env file
// (cat .env, source .env, grep KEY app/.env, ...). The Read/Edit deny rules in
// settings.json only cover Claude's file tools, not the shell.

// Exactly `.env` as a path component; `.env.example`, `.envrc` and `foo.env` don't match.
const ENV_FILE = /(^|[\s/'"=<>(:])\.env(?=$|[\s'";|&<>)])/;

let input = "";
process.stdin.on("data", (c) => (input += c));
process.stdin.on("end", () => {
  const command = JSON.parse(input).tool_input?.command ?? "";
  const match = command.match(ENV_FILE);
  if (!match) return;
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: `Blocked by global rules: the command references a .env file (\`${match[0].trim()}\`). Do not read or expose .env contents; ask the user if a value is genuinely needed.`,
    },
  }));
});
