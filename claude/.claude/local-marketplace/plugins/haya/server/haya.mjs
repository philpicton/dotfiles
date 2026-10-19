#!/usr/bin/env node
// Haya MCP server: a dependency-free port of ~/.config/opencode/tools/haya.ts.
// Speaks MCP (JSON-RPC 2.0, newline-delimited) over stdio.

import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createInterface } from "node:readline";

const execFileAsync = promisify(execFile);

const HAYA_DIR = "/Users/phil/code/haysto-v2";
const MAX_OUTPUT = 8000;
const CHECK_TIMEOUT = 300_000;
const LONG_TIMEOUT = 900_000;

const SCOPE_NOTE =
  " Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.";

function tail(text) {
  if (text.length <= MAX_OUTPUT) return text;
  return (
    `... (truncated, showing last ${MAX_OUTPUT} chars)\n` +
    text.slice(-MAX_OUTPUT)
  );
}

async function run(cmd, args, opts) {
  try {
    const { stdout, stderr } = await execFileAsync(cmd, args, {
      cwd: opts?.cwd ?? HAYA_DIR,
      timeout: opts?.timeout ?? CHECK_TIMEOUT,
      maxBuffer: 32 * 1024 * 1024,
      signal: opts?.signal,
    });
    const out = [stdout, stderr].filter(Boolean).join("\n").trim();
    return out ? tail(out) : "(no output)";
  } catch (err) {
    const out = [err?.stdout, err?.stderr].filter(Boolean).join("\n").trim();
    return `Command failed: ${cmd} ${args.join(" ")}\n${tail(out || err?.message || "unknown error")}`;
  }
}

let composeArgsCache = null;

async function composeArgs() {
  if (!composeArgsCache) {
    const { stdout } = await execFileAsync("make", ["dc"], {
      cwd: HAYA_DIR,
      timeout: 30_000,
    });
    const parts = stdout.trim().split(/\s+/).filter(Boolean);
    if (parts[0] === "docker") parts.shift();
    composeArgsCache = parts;
  }
  return composeArgsCache;
}

async function composeRun(service, inner, opts) {
  const base = await composeArgs();
  const envArgs = (opts?.env ?? []).flatMap((e) => ["-e", e]);
  return run(
    "docker",
    [
      ...base,
      "run",
      "--rm",
      "-T",
      "-q",
      "-e",
      "NPM_CONFIG_UPDATE_NOTIFIER=false",
      ...envArgs,
      service,
      ...inner,
    ],
    { timeout: opts?.timeout ?? CHECK_TIMEOUT },
  );
}

async function composeExec(service, inner, opts) {
  const base = await composeArgs();
  return run("docker", [...base, "exec", "-T", service, ...inner], {
    timeout: opts?.timeout ?? CHECK_TIMEOUT,
  });
}

async function gitFiles(appDir) {
  try {
    const { stdout } = await execFileAsync("git", ["ls-files"], {
      cwd: appDir,
      timeout: 30_000,
    });
    return stdout
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// Observability + readiness waiting
// ---------------------------------------------------------------------------

const HAYA_SERVICES = {
  api: "haysto-api",
  create: "haysto-create",
  collect: "haysto-collect",
  collaborate: "haysto-collaborate",
  nginx: "nginx",
  mysql: "haysto-api_mysql-84",
  supervisor: "haysto-api_supervisor",
};

const WAIT_DEFAULT = ["api", "create", "collect", "collaborate", "nginx"];

async function composePs() {
  try {
    const base = await composeArgs();
    const { stdout } = await execFileAsync(
      "docker",
      [...base, "ps", "--format", "json"],
      { cwd: HAYA_DIR, timeout: 30_000 },
    );
    const text = stdout.trim();
    if (!text) return [];
    try {
      const parsed = JSON.parse(text);
      return Array.isArray(parsed) ? parsed : [parsed];
    } catch {
      return text
        .split("\n")
        .filter(Boolean)
        .map((line) => {
          try {
            return JSON.parse(line);
          } catch {
            return { Service: line };
          }
        });
    }
  } catch {
    return [];
  }
}

async function probeService(svc) {
  const containers = await composePs();
  const match = containers.find((c) => c.Service === svc);
  const state = match?.State ?? "missing";
  if (!/^running$/i.test(state.trim()))
    return { svc, ready: false, detail: state };
  if (
    svc === "haysto-create" ||
    svc === "haysto-collect" ||
    svc === "haysto-collaborate"
  ) {
    const out = await composeExec(
      svc,
      [
        "node",
        "-e",
        "fetch('http://localhost:3000/').then(r=>console.log('READY '+r.status)).catch(e=>{console.log('NOTREADY '+(e.cause&&e.cause.code||e.message));process.exit(1)})",
      ],
      { timeout: 30_000 },
    );
    const m = out.match(/READY (\d+)/);
    if (m) return { svc, ready: true, detail: `serving HTTP ${m[1]}` };
    return { svc, ready: false, detail: "running, dev server not serving yet" };
  }
  return { svc, ready: true, detail: state };
}

async function waitHealthy(keys, timeoutMs, signal) {
  const svcs = keys.map((k) => HAYA_SERVICES[k] ?? k);
  const deadline = Date.now() + timeoutMs;
  const format = (rows) => rows.map((r) => `${r.svc}: ${r.detail}`).join("\n");
  let last = [];
  for (;;) {
    if (signal?.aborted)
      return `Wait aborted.\n${format(last.map((r) => ({ svc: r.svc, detail: r.ready ? r.detail : `${r.detail} (not ready)` })))}`;
    last = [];
    for (const svc of svcs) last.push(await probeService(svc));
    if (last.every((r) => r.ready)) return `All services ready:\n${format(last)}`;
    if (Date.now() >= deadline)
      return `Timed out after ${timeoutMs}ms. Still not ready:\n${format(last.filter((r) => !r.ready))}\nReady:\n${format(last.filter((r) => r.ready)) || "(none)"}`;
    await new Promise((r) => setTimeout(r, 5000));
  }
}

// ---------------------------------------------------------------------------
// App helpers
// ---------------------------------------------------------------------------

const CREATE_DIR = `${HAYA_DIR}/haysto-v2-create`;

const FILES_DESC =
  "Optional app-relative file paths to check instead of the whole project (e.g. ['components/AppFoo.vue']). Omit to check everything.";

function sanitizeFiles(files) {
  if (!files || !files.length) return null;
  return files
    .map((f) => f.trim())
    .filter((f) => f && !f.startsWith("/") && f !== ".." && !f.startsWith("../"));
}

async function targetFiles(appDir, files) {
  if (files && files.length) return sanitizeFiles(files) ?? [];
  return gitFiles(appDir);
}

async function createViaWrapper(script, extraFlags, files) {
  const targets = await targetFiles(CREATE_DIR, files);
  if (!targets.length) return "(no files to check)";
  return run(
    "sh",
    ["./scripts/run-in-docker.sh", "node", script, ...extraFlags, ...targets],
    { cwd: CREATE_DIR, timeout: LONG_TIMEOUT },
  );
}

async function nuxtLint(service, args) {
  const targets = sanitizeFiles(args.files);
  if (targets?.length) {
    return composeRun(
      service,
      ["npx", "eslint", ...(args.mode === "fix" ? ["--fix"] : []), ...targets],
      { timeout: LONG_TIMEOUT },
    );
  }
  if (args.files?.length) return "(no valid files to check — use app-relative paths)";
  return composeRun(
    service,
    ["npm", "run", args.mode === "fix" ? "lint:fix" : "lint", "--silent"],
    { timeout: LONG_TIMEOUT },
  );
}

async function nuxtFormat(service, args) {
  const targets = sanitizeFiles(args.files);
  if (targets?.length) {
    return composeRun(
      service,
      [
        "npx",
        "prettier",
        args.mode === "fix" ? "--write" : "--check",
        "--log-level",
        "warn",
        ...targets,
      ],
      { timeout: LONG_TIMEOUT },
    );
  }
  if (args.files?.length) return "(no valid files to check — use app-relative paths)";
  return composeRun(
    service,
    ["npm", "run", args.mode === "fix" ? "format:fix" : "format", "--silent"],
    { timeout: LONG_TIMEOUT },
  );
}

async function nuxtTypecheck(service, args) {
  const script = args.mode === "check" ? "typecheck" : "typecheck:baseline";
  return composeRun(service, ["npm", "run", script, "--silent"], {
    timeout: LONG_TIMEOUT,
  });
}

const NPM_INSTALLS = {
  create: { service: "haysto-create", cmd: ["npm", "install"] },
  collect: { service: "haysto-collect", cmd: ["npm", "install"] },
  collaborate: { service: "haysto-collaborate", cmd: ["npm", "install"] },
  shared: {
    service: "haysto-create",
    cmd: ["sh", "-c", "cd lib/js/haysto-v2-lib_shared && npm install"],
  },
};

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

const enumProp = (values, description, def) => ({
  type: "string",
  enum: values,
  description,
  ...(def !== undefined ? { default: def } : {}),
});
const boolProp = (description, def) => ({ type: "boolean", description, default: def });
const filesProp = { type: "array", items: { type: "string" }, description: FILES_DESC };
const checkFix = (description) => enumProp(["check", "fix"], description, "check");
const typecheckMode = enumProp(["check", "baseline"], "typecheck mode", "baseline");

const tools = [
  {
    name: "haya_up",
    description:
      "Start the Haya stack (docker compose up -d). Set installModules=true to run the non-interactive npm install for all Nuxt apps + shared lib first. Waits for services to be ready unless wait=false. Never run bare `make up` (it prompts interactively).",
    properties: {
      installModules: boolProp("Run node-modules install for all apps before starting", false),
      wait: boolProp("Wait until services are ready before returning", true),
    },
    async execute(args) {
      const parts = [];
      if (args.installModules) {
        parts.push(await run("make", ["npm", "ARGS=--install-all"], { timeout: LONG_TIMEOUT }));
      }
      parts.push(await run("make", ["dcup"], { timeout: LONG_TIMEOUT }));
      if (args.wait) parts.push(await waitHealthy(WAIT_DEFAULT, 300_000));
      return parts.join("\n---\n");
    },
  },
  {
    name: "haya_down",
    description: "Stop the Haya stack (docker compose down --remove-orphans).",
    properties: {},
    execute: () => run("make", ["down"], { timeout: CHECK_TIMEOUT }),
  },
  {
    name: "haya_restart",
    description:
      "Restart the Haya stack (down, then up). Set installModules=true to also reinstall all node modules non-interactively first. Waits for services to be ready unless wait=false.",
    properties: {
      installModules: boolProp("Reinstall all node modules before starting", false),
      wait: boolProp("Wait until services are ready before returning", true),
    },
    async execute(args) {
      const down = await run("make", ["down"], { timeout: CHECK_TIMEOUT });
      let installed = "";
      if (args.installModules) {
        installed = await run("make", ["npm", "ARGS=--install-all"], { timeout: LONG_TIMEOUT });
      }
      const up = await run("make", ["dcup"], { timeout: LONG_TIMEOUT });
      const parts = [down, installed, up].filter(Boolean);
      if (args.wait) parts.push(await waitHealthy(WAIT_DEFAULT, 300_000));
      return parts.join("\n---\n");
    },
  },
  {
    name: "haya_build",
    description: "Build Haya docker images (all, or a single service).",
    properties: {
      service: enumProp(
        ["all", "api", "create", "collect", "collaborate"],
        "Which service image to build",
        "all",
      ),
    },
    async execute(args) {
      if (args.service === "all") return run("make", ["build"], { timeout: LONG_TIMEOUT });
      const svc = args.service === "api" ? "haysto-api" : `haysto-${args.service}`;
      const base = await composeArgs();
      return run("docker", [...base, "build", svc], { timeout: LONG_TIMEOUT });
    },
  },
  {
    name: "haya_npm",
    description:
      "Install node modules for Nuxt apps (non-interactive, inside docker). Scope 'all' installs create, collect, collaborate, then shared lib last (order matters).",
    properties: {
      scope: enumProp(
        ["all", "create", "collect", "collaborate", "shared"],
        "Which project to install node modules for",
        "all",
      ),
    },
    async execute(args) {
      const order =
        args.scope === "all" ? ["create", "collect", "collaborate", "shared"] : [args.scope];
      const outputs = [];
      for (const key of order) {
        const { service, cmd } = NPM_INSTALLS[key];
        outputs.push(`## ${key}\n` + (await composeRun(service, cmd, { timeout: LONG_TIMEOUT })));
      }
      return outputs.join("\n---\n");
    },
  },
  {
    name: "haya_exec_api",
    description:
      "Run a non-interactive shell command inside the haysto-api container (e.g. 'php artisan about', 'php -v', 'ls storage/logs'). Requires the stack to be up (haya_up). Local env only. Never use for interactive shells.",
    properties: {
      command: { type: "string", description: "Shell command to run inside haysto-api" },
      timeoutMs: { type: "number", description: "Timeout in ms (default 120000)" },
    },
    required: ["command"],
    execute: (args) =>
      composeExec("haysto-api", ["sh", "-c", args.command], {
        timeout: args.timeoutMs ?? 120_000,
      }),
  },
  {
    name: "haya_status",
    description:
      "Show Haya container status (service, state, published ports). Read-only. Call this before exec-based tools to check the stack is up.",
    properties: {},
    async execute() {
      const containers = await composePs();
      if (!containers.length) return "No containers found (stack may be down — see haya_up).";
      return containers
        .map((c) => {
          const svc = c.Service ?? c.Name ?? "?";
          const state = c.State ?? c.Status ?? "?";
          const pubs = Array.isArray(c.Publishers)
            ? [
                ...new Set(
                  c.Publishers.map((p) =>
                    p?.PublishedPort && String(p.PublishedPort) !== "0"
                      ? `${p.PublishedPort}->${p.TargetPort}`
                      : `${p?.TargetPort} (internal)`,
                  ).filter((s) => s && s !== "undefined (internal)"),
                ),
              ].join(", ")
            : "";
          return `${svc}: ${state}${pubs ? ` (${pubs})` : ""}`;
        })
        .join("\n");
    },
  },
  {
    name: "haya_logs",
    description:
      "Read recent logs for a Haya service. Read-only. Use tail to limit lines and contains to filter (e.g. 'ERROR').",
    properties: {
      service: enumProp(
        ["api", "create", "collect", "collaborate", "nginx", "mysql", "supervisor"],
        "Which service's logs to read",
      ),
      tail: { type: "number", description: "Number of recent lines (default 100, max 2000)", default: 100 },
      contains: { type: "string", description: "Only show lines containing this substring" },
    },
    required: ["service"],
    async execute(args) {
      const base = await composeArgs();
      const lines = Math.max(1, Math.min(args.tail ?? 100, 2000));
      const out = await run(
        "docker",
        [...base, "logs", "--no-color", "--tail", String(lines), HAYA_SERVICES[args.service]],
        { timeout: 60_000 },
      );
      const clean = out.replace(/\u001b\[[0-9;]*m/g, "");
      if (!args.contains) return clean;
      const needle = args.contains.toLowerCase();
      const hits = clean.split("\n").filter((line) => line.toLowerCase().includes(needle));
      return hits.length ? tail(hits.join("\n")) : "(no matching lines)";
    },
  },
  {
    name: "haya_wait_healthy",
    description:
      "Wait until Haya services are running and Nuxt dev servers answer HTTP. Polls every 5s until timeout. Use after haya_up/haya_restart before API-dependent work.",
    properties: {
      services: {
        type: "array",
        items: { type: "string", enum: ["api", "create", "collect", "collaborate", "nginx"] },
        description: "Which services to wait for",
        default: WAIT_DEFAULT,
      },
      timeoutMs: { type: "number", description: "Max wait in ms (default 300000)", default: 300_000 },
    },
    execute: (args, signal) =>
      waitHealthy(args.services ?? WAIT_DEFAULT, args.timeoutMs ?? 300_000, signal),
  },
  {
    name: "haya_create_lint",
    description:
      "Run eslint on haysto-v2-create inside docker. Mode check reports errors, fix auto-fixes them. Pass files to check only those paths.",
    properties: { mode: checkFix("check or auto-fix"), files: filesProp },
    execute: (args) =>
      createViaWrapper("scripts/eslint.mjs", args.mode === "fix" ? ["--fix"] : [], args.files),
  },
  {
    name: "haya_create_format",
    description:
      "Run prettier on haysto-v2-create inside docker. Mode check reports diffs, fix rewrites files. Pass files to check only those paths.",
    properties: { mode: checkFix("check or write fixes"), files: filesProp },
    execute: (args) =>
      createViaWrapper("scripts/prettier.mjs", args.mode === "fix" ? ["--write"] : [], args.files),
  },
  {
    name: "haya_create_baseline",
    description:
      "TypeScript baseline check for haysto-v2-create inside docker: fails only on new errors vs the baseline. The baseline file is maintainer-managed — fix the code, never rewrite the baseline.",
    properties: { files: filesProp },
    execute: (args) => createViaWrapper("scripts/typescript-baseline-check.mjs", [], args.files),
  },
  {
    name: "haya_collect_lint",
    description:
      "Run eslint on haysto-v2-collect inside docker. Mode check reports, fix auto-fixes. Pass files to lint only those paths.",
    properties: { mode: checkFix("check or auto-fix"), files: filesProp },
    execute: (args) => nuxtLint("haysto-collect", args),
  },
  {
    name: "haya_collect_format",
    description:
      "Run prettier on haysto-v2-collect inside docker. Mode check reports, fix rewrites. Pass files to check only those paths.",
    properties: { mode: checkFix("check or write fixes"), files: filesProp },
    execute: (args) => nuxtFormat("haysto-collect", args),
  },
  {
    name: "haya_collect_typecheck",
    description:
      "Typecheck haysto-v2-collect inside docker. check = full vue-tsc, baseline = fail only on new errors vs baseline. The baseline file is maintainer-managed — fix the code, never rewrite the baseline.",
    properties: { mode: typecheckMode },
    execute: (args) => nuxtTypecheck("haysto-collect", args),
  },
  {
    name: "haya_collaborate_lint",
    description:
      "Run eslint on haysto-v2-collaborate inside docker. Mode check reports, fix auto-fixes. Pass files to lint only those paths.",
    properties: { mode: checkFix("check or auto-fix"), files: filesProp },
    execute: (args) => nuxtLint("haysto-collaborate", args),
  },
  {
    name: "haya_collaborate_format",
    description:
      "Run prettier on haysto-v2-collaborate inside docker. Mode check reports, fix rewrites. Pass files to check only those paths.",
    properties: { mode: checkFix("check or write fixes"), files: filesProp },
    execute: (args) => nuxtFormat("haysto-collaborate", args),
  },
  {
    name: "haya_collaborate_typecheck",
    description:
      "Typecheck haysto-v2-collaborate inside docker. check = full vue-tsc, baseline = fail only on new errors vs baseline. The baseline file is maintainer-managed — fix the code, never rewrite the baseline.",
    properties: { mode: typecheckMode },
    execute: (args) => nuxtTypecheck("haysto-collaborate", args),
  },
  {
    name: "haya_phpstan",
    description:
      "Run PHPStan analysis inside haysto-api. Requires the stack to be up. Optional path limits analysis (e.g. 'app/Services').",
    properties: {
      path: { type: "string", description: "Sub-path to analyse, relative to haysto-v2-api" },
    },
    execute: (args) =>
      run("make", ["phpstan", ...(args.path ? ["dir=" + args.path] : [])], {
        timeout: LONG_TIMEOUT,
      }),
  },
  {
    name: "haya_phpstan_baseline",
    description:
      "Regenerate the PHPStan baseline inside haysto-api (make baseline). Requires the stack to be up. Use sparingly — it rewrites baselines.",
    properties: {},
    execute: () => run("make", ["baseline"], { timeout: LONG_TIMEOUT }),
  },
  {
    name: "haya_migrate",
    description: "Run database migrations inside haysto-api (make migrate). Requires the stack to be up.",
    properties: {},
    execute: () => run("make", ["migrate"], { timeout: CHECK_TIMEOUT }),
  },
  {
    name: "haya_api_seed",
    description:
      "Run a non-destructive API seeder: cases (bulk dev cases), case (single dev case), deployment-safe, fact-find, or permissions reseed. Requires the stack to be up.",
    properties: {
      target: enumProp(
        ["cases", "case", "deployment-safe", "fact-find", "permissions"],
        "Which seeder to run",
      ),
    },
    required: ["target"],
    execute(args) {
      const targets = {
        cases: "cases",
        case: "case",
        "deployment-safe": "seed_deployment_safe",
        "fact-find": "seed_fact_find",
        permissions: "update_permissions",
      };
      return run("make", [targets[args.target]], { timeout: LONG_TIMEOUT });
    },
  },
];

const toolsByName = new Map(tools.map((t) => [t.name, t]));

function withDefaults(tool, args) {
  const out = { ...(args ?? {}) };
  for (const [key, schema] of Object.entries(tool.properties)) {
    if (out[key] === undefined && schema.default !== undefined) out[key] = schema.default;
  }
  return out;
}

// ---------------------------------------------------------------------------
// MCP stdio transport
// ---------------------------------------------------------------------------

const inflight = new Map();

function send(msg) {
  process.stdout.write(JSON.stringify({ jsonrpc: "2.0", ...msg }) + "\n");
}

async function handle(msg) {
  const { id, method, params } = msg;
  switch (method) {
    case "initialize":
      return send({
        id,
        result: {
          protocolVersion: params?.protocolVersion ?? "2025-06-18",
          capabilities: { tools: {} },
          serverInfo: { name: "haya", version: "1.0.0" },
        },
      });
    case "ping":
      return send({ id, result: {} });
    case "tools/list":
      return send({
        id,
        result: {
          tools: tools.map((t) => ({
            name: t.name,
            description: t.description + SCOPE_NOTE,
            inputSchema: {
              type: "object",
              properties: t.properties,
              ...(t.required ? { required: t.required } : {}),
            },
          })),
        },
      });
    case "tools/call": {
      const tool = toolsByName.get(params?.name);
      if (!tool) {
        return send({ id, error: { code: -32602, message: `Unknown tool: ${params?.name}` } });
      }
      const controller = new AbortController();
      inflight.set(id, controller);
      try {
        const text = await tool.execute(withDefaults(tool, params.arguments), controller.signal);
        send({ id, result: { content: [{ type: "text", text }] } });
      } catch (err) {
        send({
          id,
          result: { content: [{ type: "text", text: String(err?.message ?? err) }], isError: true },
        });
      } finally {
        inflight.delete(id);
      }
      return;
    }
    case "notifications/cancelled":
      inflight.get(params?.requestId)?.abort();
      return;
    default:
      if (id !== undefined) {
        send({ id, error: { code: -32601, message: `Method not found: ${method}` } });
      }
  }
}

createInterface({ input: process.stdin }).on("line", (line) => {
  if (!line.trim()) return;
  let msg;
  try {
    msg = JSON.parse(line);
  } catch {
    return send({ id: null, error: { code: -32700, message: "Parse error" } });
  }
  handle(msg);
});
