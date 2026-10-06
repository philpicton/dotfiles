import { tool } from "@opencode-ai/plugin";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const HAYA_DIR = "/Users/phil/code/haysto-v2";
const MAX_OUTPUT = 8000;
const CHECK_TIMEOUT = 300_000;
const LONG_TIMEOUT = 900_000;

function tail(text: string): string {
  if (text.length <= MAX_OUTPUT) return text;
  return (
    `... (truncated, showing last ${MAX_OUTPUT} chars)\n` +
    text.slice(-MAX_OUTPUT)
  );
}

async function run(
  cmd: string,
  args: string[],
  opts?: { cwd?: string; timeout?: number },
): Promise<string> {
  try {
    const { stdout, stderr } = await execFileAsync(cmd, args, {
      cwd: opts?.cwd ?? HAYA_DIR,
      timeout: opts?.timeout ?? CHECK_TIMEOUT,
      maxBuffer: 32 * 1024 * 1024,
    });
    const out = [stdout, stderr].filter(Boolean).join("\n").trim();
    return out ? tail(out) : "(no output)";
  } catch (err: any) {
    const out = [err?.stdout, err?.stderr]
      .filter(Boolean)
      .join("\n")
      .trim();
    return `Command failed: ${cmd} ${args.join(" ")}\n${tail(out || err?.message || "unknown error")}`;
  }
}

let composeArgsCache: string[] | null = null;

async function composeArgs(): Promise<string[]> {
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

async function composeRun(
  service: string,
  inner: string[],
  opts?: { timeout?: number; env?: string[] },
): Promise<string> {
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

async function composeExec(
  service: string,
  inner: string[],
  opts?: { timeout?: number },
): Promise<string> {
  const base = await composeArgs();
  return run("docker", [...base, "exec", "-T", service, ...inner], {
    timeout: opts?.timeout ?? CHECK_TIMEOUT,
  });
}

async function gitFiles(appDir: string): Promise<string[]> {
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
// Stack lifecycle (applies to all repos)
// ---------------------------------------------------------------------------

export const haya_up = tool({
  description:
    "Start the Haya stack (docker compose up -d). Set installModules=true to run the non-interactive npm install for all Nuxt apps + shared lib first. Waits for services to be ready unless wait=false. Never run bare `make up` (it prompts interactively). Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    installModules: tool.schema
      .boolean()
      .describe("Run node-modules install for all apps before starting")
      .default(false),
    wait: tool.schema
      .boolean()
      .describe("Wait until services are ready before returning")
      .default(true),
  },
  async execute(args) {
    if (args.installModules) {
      const installed = await run("make", ["npm", "ARGS=--install-all"], {
        timeout: LONG_TIMEOUT,
      });
      const started = await run("make", ["dcup"], {
        timeout: LONG_TIMEOUT,
      });
      if (!args.wait) return `${installed}\n---\n${started}`;
      const healthy = await waitHealthy(WAIT_DEFAULT, 300_000);
      return `${installed}\n---\n${started}\n---\n${healthy}`;
    }
    const started = await run("make", ["dcup"], { timeout: LONG_TIMEOUT });
    if (!args.wait) return started;
    const healthy = await waitHealthy(WAIT_DEFAULT, 300_000);
    return `${started}\n---\n${healthy}`;
  },
});

export const haya_down = tool({
  description: "Stop the Haya stack (docker compose down --remove-orphans). Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {},
  async execute() {
    return run("make", ["down"], { timeout: CHECK_TIMEOUT });
  },
});

export const haya_restart = tool({
  description:
    "Restart the Haya stack (down, then up). Set installModules=true to also reinstall all node modules non-interactively first. Waits for services to be ready unless wait=false. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    installModules: tool.schema
      .boolean()
      .describe("Reinstall all node modules before starting")
      .default(false),
    wait: tool.schema
      .boolean()
      .describe("Wait until services are ready before returning")
      .default(true),
  },
  async execute(args) {
    const down = await run("make", ["down"], { timeout: CHECK_TIMEOUT });
    let installed = "";
    if (args.installModules) {
      installed = await run("make", ["npm", "ARGS=--install-all"], {
        timeout: LONG_TIMEOUT,
      });
    }
    const up = await run("make", ["dcup"], { timeout: LONG_TIMEOUT });
    const parts = [down, installed, up].filter(Boolean);
    if (args.wait) {
      parts.push(await waitHealthy(WAIT_DEFAULT, 300_000));
    }
    return parts.join("\n---\n");
  },
});

export const haya_build = tool({
  description: "Build Haya docker images (all, or a single service). Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    service: tool.schema
      .enum(["all", "api", "create", "collect", "collaborate"])
      .describe("Which service image to build")
      .default("all"),
  },
  async execute(args) {
    if (args.service === "all") {
      return run("make", ["build"], { timeout: LONG_TIMEOUT });
    }
    const svc =
      args.service === "api"
        ? "haysto-api"
        : `haysto-${args.service}`;
    const base = await composeArgs();
    return run("docker", [...base, "build", svc], {
      timeout: LONG_TIMEOUT,
    });
  },
});

const NPM_INSTALLS: Record<string, { service: string; cmd: string[] }> = {
  create: { service: "haysto-create", cmd: ["npm", "install"] },
  collect: { service: "haysto-collect", cmd: ["npm", "install"] },
  collaborate: { service: "haysto-collaborate", cmd: ["npm", "install"] },
  shared: {
    service: "haysto-create",
    cmd: ["sh", "-c", "cd lib/js/haysto-v2-lib_shared && npm install"],
  },
};

export const haya_npm = tool({
  description:
    "Install node modules for Nuxt apps (non-interactive, inside docker). Scope 'all' installs create, collect, collaborate, then shared lib last (order matters). Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    scope: tool.schema
      .enum(["all", "create", "collect", "collaborate", "shared"])
      .describe("Which project to install node modules for")
      .default("all"),
  },
  async execute(args) {
    const order =
      args.scope === "all"
        ? ["create", "collect", "collaborate", "shared"]
        : [args.scope];
    const outputs: string[] = [];
    for (const key of order) {
      const { service, cmd } = NPM_INSTALLS[key];
      outputs.push(
        `## ${key}\n` +
          (await composeRun(service, cmd, { timeout: LONG_TIMEOUT })),
      );
    }
    return outputs.join("\n---\n");
  },
});

export const haya_exec_api = tool({
  description:
    "Run a non-interactive shell command inside the haysto-api container (e.g. 'php artisan about', 'php -v', 'ls storage/logs'). Requires the stack to be up (haya_up). Local env only. Never use for interactive shells. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    command: tool.schema
      .string()
      .describe("Shell command to run inside haysto-api"),
    timeoutMs: tool.schema
      .number()
      .describe("Timeout in ms (default 120000)")
      .optional(),
  },
  async execute(args) {
    return composeExec("haysto-api", ["sh", "-c", args.command], {
      timeout: args.timeoutMs ?? 120_000,
    });
  },
});

// ---------------------------------------------------------------------------
// Observability (read-only) + readiness waiting
// ---------------------------------------------------------------------------

const HAYA_SERVICES: Record<string, string> = {
  api: "haysto-api",
  create: "haysto-create",
  collect: "haysto-collect",
  collaborate: "haysto-collaborate",
  nginx: "nginx",
  mysql: "haysto-api_mysql-84",
  supervisor: "haysto-api_supervisor",
};

const WAIT_DEFAULT = ["api", "create", "collect", "collaborate", "nginx"];

async function composePs(): Promise<any[]> {
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

export const haya_status = tool({
  description:
    "Show Haya container status (service, state, published ports). Read-only. Call this before exec-based tools to check the stack is up. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {},
  async execute() {
    const containers = await composePs();
    if (!containers.length)
      return "No containers found (stack may be down — see haya_up).";
    return containers
      .map((c) => {
        const svc = c.Service ?? c.Name ?? "?";
        const state = c.State ?? c.Status ?? "?";
        const pubs = Array.isArray(c.Publishers)
          ? [
              ...new Set(
                c.Publishers.map((p: any) =>
                  p?.PublishedPort && String(p.PublishedPort) !== "0"
                    ? `${p.PublishedPort}->${p.TargetPort}`
                    : `${p?.TargetPort} (internal)`,
                ).filter(
                  (s: string) => s && s !== "undefined (internal)",
                ),
              ),
            ].join(", ")
          : "";
        return `${svc}: ${state}${pubs ? ` (${pubs})` : ""}`;
      })
      .join("\n");
  },
});

export const haya_logs = tool({
  description:
    "Read recent logs for a Haya service. Read-only. Use tail to limit lines and contains to filter (e.g. 'ERROR'). Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    service: tool.schema
      .enum([
        "api",
        "create",
        "collect",
        "collaborate",
        "nginx",
        "mysql",
        "supervisor",
      ])
      .describe("Which service's logs to read"),
    tail: tool.schema
      .number()
      .describe("Number of recent lines (default 100, max 2000)")
      .default(100),
    contains: tool.schema
      .string()
      .describe("Only show lines containing this substring")
      .optional(),
  },
  async execute(args) {
    const base = await composeArgs();
    const out = await run(
      "docker",
      [
        ...base,
        "logs",
        "--no-color",
        "--tail",
        String(Math.max(1, Math.min(args.tail, 2000))),
        HAYA_SERVICES[args.service],
      ],
      { timeout: 60_000 },
    );
    const clean = out.replace(/\u001b\[[0-9;]*m/g, "");
    if (!args.contains) return clean;
    const needle = args.contains.toLowerCase();
    const hits = clean
      .split("\n")
      .filter((line) => line.toLowerCase().includes(needle));
    return hits.length ? tail(hits.join("\n")) : "(no matching lines)";
  },
});

async function probeService(
  svc: string,
): Promise<{ svc: string; ready: boolean; detail: string }> {
  const containers = await composePs();
  const match = containers.find((c) => c.Service === svc);
  const state: string = match?.State ?? "missing";
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

async function waitHealthy(
  keys: string[],
  timeoutMs: number,
  signal?: AbortSignal,
): Promise<string> {
  const svcs = keys.map((k) => HAYA_SERVICES[k] ?? k);
  const deadline = Date.now() + timeoutMs;
  const format = (rows: { svc: string; detail: string }[]) =>
    rows.map((r) => `${r.svc}: ${r.detail}`).join("\n");
  let last: { svc: string; ready: boolean; detail: string }[] = [];
  for (;;) {
    if (signal?.aborted)
      return `Wait aborted.\n${format(last.map((r) => ({ svc: r.svc, detail: r.ready ? r.detail : `${r.detail} (not ready)` })))}`;
    last = [];
    for (const svc of svcs) last.push(await probeService(svc));
    if (last.every((r) => r.ready))
      return `All services ready:\n${format(last)}`;
    if (Date.now() >= deadline)
      return `Timed out after ${timeoutMs}ms. Still not ready:\n${format(last.filter((r) => !r.ready))}\nReady:\n${format(last.filter((r) => r.ready)) || "(none)"}`;
    await new Promise((r) => setTimeout(r, 5000));
  }
}

export const haya_wait_healthy = tool({
  description:
    "Wait until Haya services are running and Nuxt dev servers answer HTTP. Polls every 5s until timeout. Use after haya_up/haya_restart before API-dependent work. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    services: tool.schema
      .array(
        tool.schema.enum(["api", "create", "collect", "collaborate", "nginx"]),
      )
      .describe("Which services to wait for")
      .default(["api", "create", "collect", "collaborate", "nginx"]),
    timeoutMs: tool.schema
      .number()
      .describe("Max wait in ms (default 300000)")
      .default(300_000),
  },
  async execute(args, context) {
    return waitHealthy(args.services, args.timeoutMs, context?.abort);
  },
});

// ---------------------------------------------------------------------------
// haysto-v2-create (host wrapper delegates into docker via run-in-docker.sh)
// ---------------------------------------------------------------------------

const CREATE_DIR = `${HAYA_DIR}/haysto-v2-create`;

const FILES_DESC =
  "Optional app-relative file paths to check instead of the whole project (e.g. ['components/AppFoo.vue']). Omit to check everything.";

function sanitizeFiles(files: string[] | undefined): string[] | null {
  if (!files || !files.length) return null;
  return files
    .map((f) => f.trim())
    .filter(
      (f) =>
        f && !f.startsWith("/") && f !== ".." && !f.startsWith("../"),
    );
}

async function targetFiles(
  appDir: string,
  files?: string[],
): Promise<string[]> {
  if (files && files.length) return sanitizeFiles(files) ?? [];
  return gitFiles(appDir);
}

async function createViaWrapper(
  script: string,
  extraFlags: string[],
  files?: string[],
): Promise<string> {
  const targets = await targetFiles(CREATE_DIR, files);
  if (!targets.length) return "(no files to check)";
  return run(
    "sh",
    ["./scripts/run-in-docker.sh", "node", script, ...extraFlags, ...targets],
    { cwd: CREATE_DIR, timeout: LONG_TIMEOUT },
  );
}

export const haya_create_lint = tool({
  description:
    "Run eslint on haysto-v2-create inside docker. Mode check reports errors, fix auto-fixes them. Pass files to check only those paths. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    mode: tool.schema
      .enum(["check", "fix"])
      .describe("check or auto-fix")
      .default("check"),
    files: tool.schema
      .array(tool.schema.string())
      .describe(FILES_DESC)
      .optional(),
  },
  async execute(args) {
    return createViaWrapper(
      "scripts/eslint.mjs",
      args.mode === "fix" ? ["--fix"] : [],
      args.files,
    );
  },
});

export const haya_create_format = tool({
  description:
    "Run prettier on haysto-v2-create inside docker. Mode check reports diffs, fix rewrites files. Pass files to check only those paths. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    mode: tool.schema
      .enum(["check", "fix"])
      .describe("check or write fixes")
      .default("check"),
    files: tool.schema
      .array(tool.schema.string())
      .describe(FILES_DESC)
      .optional(),
  },
  async execute(args) {
    return createViaWrapper(
      "scripts/prettier.mjs",
      args.mode === "fix" ? ["--write"] : [],
      args.files,
    );
  },
});

export const haya_create_baseline = tool({
  description:
    "TypeScript baseline check for haysto-v2-create inside docker: fails only on new errors vs the baseline. The baseline file is maintainer-managed — fix the code, never rewrite the baseline. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    files: tool.schema
      .array(tool.schema.string())
      .describe(FILES_DESC)
      .optional(),
  },
  async execute(args) {
    return createViaWrapper(
      "scripts/typescript-baseline-check.mjs",
      [],
      args.files,
    );
  },
});

// ---------------------------------------------------------------------------
// haysto-v2-collect (npm scripts run directly inside the container)
// ---------------------------------------------------------------------------

export const haya_collect_lint = tool({
  description:
    "Run eslint on haysto-v2-collect inside docker. Mode check reports, fix auto-fixes. Pass files to lint only those paths. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    mode: tool.schema
      .enum(["check", "fix"])
      .describe("check or auto-fix")
      .default("check"),
    files: tool.schema
      .array(tool.schema.string())
      .describe(FILES_DESC)
      .optional(),
  },
  async execute(args) {
    const targets = sanitizeFiles(args.files);
    if (targets?.length) {
      return composeRun(
        "haysto-collect",
        [
          "npx",
          "eslint",
          ...(args.mode === "fix" ? ["--fix"] : []),
          ...targets,
        ],
        { timeout: LONG_TIMEOUT },
      );
    }
    if (args.files?.length) return "(no valid files to check — use app-relative paths)";
    return composeRun(
      "haysto-collect",
      ["npm", "run", args.mode === "fix" ? "lint:fix" : "lint", "--silent"],
      { timeout: LONG_TIMEOUT },
    );
  },
});

export const haya_collect_format = tool({
  description:
    "Run prettier on haysto-v2-collect inside docker. Mode check reports, fix rewrites. Pass files to check only those paths. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    mode: tool.schema
      .enum(["check", "fix"])
      .describe("check or write fixes")
      .default("check"),
    files: tool.schema
      .array(tool.schema.string())
      .describe(FILES_DESC)
      .optional(),
  },
  async execute(args) {
    const targets = sanitizeFiles(args.files);
    if (targets?.length) {
      return composeRun(
        "haysto-collect",
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
      "haysto-collect",
      ["npm", "run", args.mode === "fix" ? "format:fix" : "format", "--silent"],
      { timeout: LONG_TIMEOUT },
    );
  },
});

export const haya_collect_typecheck = tool({
  description:
    "Typecheck haysto-v2-collect inside docker. check = full vue-tsc, baseline = fail only on new errors vs baseline. The baseline file is maintainer-managed — fix the code, never rewrite the baseline. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    mode: tool.schema
      .enum(["check", "baseline"])
      .describe("typecheck mode")
      .default("baseline"),
  },
  async execute(args) {
    if (args.mode === "check") {
      return composeRun(
        "haysto-collect",
        ["npm", "run", "typecheck", "--silent"],
        { timeout: LONG_TIMEOUT },
      );
    }
    return composeRun(
      "haysto-collect",
      ["npm", "run", "typecheck:baseline", "--silent"],
      { timeout: LONG_TIMEOUT },
    );
  },
});

// ---------------------------------------------------------------------------
// haysto-v2-collaborate (same shape as collect)
// ---------------------------------------------------------------------------

export const haya_collaborate_lint = tool({
  description:
    "Run eslint on haysto-v2-collaborate inside docker. Mode check reports, fix auto-fixes. Pass files to lint only those paths. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    mode: tool.schema
      .enum(["check", "fix"])
      .describe("check or auto-fix")
      .default("check"),
    files: tool.schema
      .array(tool.schema.string())
      .describe(FILES_DESC)
      .optional(),
  },
  async execute(args) {
    const targets = sanitizeFiles(args.files);
    if (targets?.length) {
      return composeRun(
        "haysto-collaborate",
        [
          "npx",
          "eslint",
          ...(args.mode === "fix" ? ["--fix"] : []),
          ...targets,
        ],
        { timeout: LONG_TIMEOUT },
      );
    }
    if (args.files?.length) return "(no valid files to check — use app-relative paths)";
    return composeRun(
      "haysto-collaborate",
      ["npm", "run", args.mode === "fix" ? "lint:fix" : "lint", "--silent"],
      { timeout: LONG_TIMEOUT },
    );
  },
});

export const haya_collaborate_format = tool({
  description:
    "Run prettier on haysto-v2-collaborate inside docker. Mode check reports, fix rewrites. Pass files to check only those paths. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    mode: tool.schema
      .enum(["check", "fix"])
      .describe("check or write fixes")
      .default("check"),
    files: tool.schema
      .array(tool.schema.string())
      .describe(FILES_DESC)
      .optional(),
  },
  async execute(args) {
    const targets = sanitizeFiles(args.files);
    if (targets?.length) {
      return composeRun(
        "haysto-collaborate",
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
      "haysto-collaborate",
      ["npm", "run", args.mode === "fix" ? "format:fix" : "format", "--silent"],
      { timeout: LONG_TIMEOUT },
    );
  },
});

export const haya_collaborate_typecheck = tool({
  description:
    "Typecheck haysto-v2-collaborate inside docker. check = full vue-tsc, baseline = fail only on new errors vs baseline. The baseline file is maintainer-managed — fix the code, never rewrite the baseline. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    mode: tool.schema
      .enum(["check", "baseline"])
      .describe("typecheck mode")
      .default("baseline"),
  },
  async execute(args) {
    if (args.mode === "check") {
      return composeRun(
        "haysto-collaborate",
        ["npm", "run", "typecheck", "--silent"],
        { timeout: LONG_TIMEOUT },
      );
    }
    return composeRun(
      "haysto-collaborate",
      ["npm", "run", "typecheck:baseline", "--silent"],
      { timeout: LONG_TIMEOUT },
    );
  },
});

// ---------------------------------------------------------------------------
// PHP / API-only tools
// ---------------------------------------------------------------------------

export const haya_phpstan = tool({
  description:
    "Run PHPStan analysis inside haysto-api. Requires the stack to be up. Optional path limits analysis (e.g. 'app/Services'). Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    path: tool.schema
      .string()
      .describe("Sub-path to analyse, relative to haysto-v2-api")
      .optional(),
  },
  async execute(args) {
    const target = args.path ? ["dir=" + args.path] : [];
    return run("make", ["phpstan", ...target], { timeout: LONG_TIMEOUT });
  },
});

export const haya_phpstan_baseline = tool({
  description:
    "Regenerate the PHPStan baseline inside haysto-api (make baseline). Requires the stack to be up. Use sparingly — it rewrites baselines. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {},
  async execute() {
    return run("make", ["baseline"], { timeout: LONG_TIMEOUT });
  },
});

export const haya_migrate = tool({
  description:     "Run database migrations inside haysto-api (make migrate). Requires the stack to be up. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {},
  async execute() {
    return run("make", ["migrate"], { timeout: CHECK_TIMEOUT });
  },
});

export const haya_api_seed = tool({
  description:
    "Run a non-destructive API seeder: cases (bulk dev cases), case (single dev case), deployment-safe, fact-find, or permissions reseed. Requires the stack to be up. Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.",
  args: {
    target: tool.schema
      .enum(["cases", "case", "deployment-safe", "fact-find", "permissions"])
      .describe("Which seeder to run"),
  },
  async execute(args) {
    const target =
      args.target === "cases"
        ? "cases"
        : args.target === "case"
          ? "case"
          : args.target === "deployment-safe"
            ? "seed_deployment_safe"
            : args.target === "fact-find"
              ? "seed_fact_find"
              : "update_permissions";
    return run("make", [target], { timeout: LONG_TIMEOUT });
  },
});
