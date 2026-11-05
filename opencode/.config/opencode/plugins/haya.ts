import { Plugin } from "@opencode/plugin";
import { Effect, Schema } from "effect";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

const HAYA_DIR = "/Users/phil/code/haysto-v2";
const MAX_OUTPUT = 8000;
const CHECK_TIMEOUT = 300_000;
const LONG_TIMEOUT = 900_000;

const SCOPE_NOTE =
  "Only for work in the Haysto Haya monorepo (~/code/haysto-v2 and its haysto-v2-create/collect/collaborate sub-repos); do not use in other projects.";

function tail(text: string): string {
  if (text.length <= MAX_OUTPUT) return text;
  return (
    `... (truncated, showing last ${MAX_OUTPUT} chars)\n` +
    text.slice(-MAX_OUTPUT)
  );
}

interface ExecFailure {
  stdout?: string;
  stderr?: string;
  message?: string;
}

function isExecFailure(error: unknown): error is ExecFailure {
  return typeof error === "object" && error !== null;
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
  } catch (error: unknown) {
    const failure = isExecFailure(error) ? error : {};
    const out = [failure.stdout, failure.stderr]
      .filter(Boolean)
      .join("\n")
      .trim();
    return `Command failed: ${cmd} ${args.join(" ")}\n${tail(out || failure.message || "unknown error")}`;
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
  const envArgs = (opts?.env ?? []).flatMap((entry) => ["-e", entry]);
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
      .map((line) => line.trim())
      .filter(Boolean);
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// Container status + readiness
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

const WAIT_SERVICES = ["api", "create", "collect", "collaborate", "nginx"] as const;

interface ComposePublisher {
  PublishedPort?: number | string;
  TargetPort?: number | string;
}

interface ComposeContainer {
  Service?: string;
  Name?: string;
  State?: string;
  Status?: string;
  Publishers?: ComposePublisher[];
}

function toContainer(value: unknown): ComposeContainer {
  return typeof value === "object" && value !== null ? value : {};
}

async function composePs(): Promise<ComposeContainer[]> {
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
      const parsed: unknown = JSON.parse(text);
      return Array.isArray(parsed) ? parsed.map(toContainer) : [toContainer(parsed)];
    } catch {
      return text
        .split("\n")
        .filter(Boolean)
        .map((line) => {
          try {
            return toContainer(JSON.parse(line));
          } catch {
            return { Service: line };
          }
        });
    }
  } catch {
    return [];
  }
}

function formatPublishers(publishers: ComposePublisher[] | undefined): string {
  if (!Array.isArray(publishers)) return "";
  const ports = publishers
    .map((publisher) =>
      publisher.PublishedPort && String(publisher.PublishedPort) !== "0"
        ? `${publisher.PublishedPort}->${publisher.TargetPort}`
        : `${publisher.TargetPort} (internal)`,
    )
    .filter((port) => port !== "undefined (internal)");
  return [...new Set(ports)].join(", ");
}

interface ProbeResult {
  svc: string;
  ready: boolean;
  detail: string;
}

async function probeService(svc: string): Promise<ProbeResult> {
  const containers = await composePs();
  const match = containers.find((container) => container.Service === svc);
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
    const match = out.match(/READY (\d+)/);
    if (match) return { svc, ready: true, detail: `serving HTTP ${match[1]}` };
    return { svc, ready: false, detail: "running, dev server not serving yet" };
  }
  return { svc, ready: true, detail: state };
}

async function waitHealthy(
  keys: readonly string[],
  timeoutMs: number,
  signal?: AbortSignal,
): Promise<string> {
  const svcs = keys.map((key) => HAYA_SERVICES[key] ?? key);
  const deadline = Date.now() + timeoutMs;
  const format = (rows: { svc: string; detail: string }[]) =>
    rows.map((row) => `${row.svc}: ${row.detail}`).join("\n");
  let last: ProbeResult[] = [];
  for (;;) {
    if (signal?.aborted)
      return `Wait aborted.\n${format(last.map((row) => ({ svc: row.svc, detail: row.ready ? row.detail : `${row.detail} (not ready)` })))}`;
    last = [];
    for (const svc of svcs) last.push(await probeService(svc));
    if (last.every((row) => row.ready))
      return `All services ready:\n${format(last)}`;
    if (Date.now() >= deadline)
      return `Timed out after ${timeoutMs}ms. Still not ready:\n${format(last.filter((row) => !row.ready))}\nReady:\n${format(last.filter((row) => row.ready)) || "(none)"}`;
    await new Promise((resolve) => setTimeout(resolve, 5000));
  }
}

// ---------------------------------------------------------------------------
// App checks (create / collect go through run-in-docker.sh)
// ---------------------------------------------------------------------------

const CREATE_DIR = `${HAYA_DIR}/haysto-v2-create`;
const COLLECT_DIR = `${HAYA_DIR}/haysto-v2-collect`;

function sanitizeFiles(files: readonly string[] | undefined): string[] | null {
  if (!files || !files.length) return null;
  return files
    .map((file) => file.trim())
    .filter(
      (file) =>
        file && !file.startsWith("/") && file !== ".." && !file.startsWith("../"),
    );
}

async function targetFiles(
  appDir: string,
  files?: readonly string[],
): Promise<string[]> {
  if (files && files.length) return sanitizeFiles(files) ?? [];
  return gitFiles(appDir);
}

async function viaWrapper(
  appDir: string,
  script: string,
  extraFlags: string[],
  files?: readonly string[],
): Promise<string> {
  const targets = await targetFiles(appDir, files);
  if (!targets.length) return "(no files to check)";
  return run(
    "sh",
    ["./scripts/run-in-docker.sh", "node", script, ...extraFlags, ...targets],
    { cwd: appDir, timeout: LONG_TIMEOUT },
  );
}

// ---------------------------------------------------------------------------
// Input schemas
// ---------------------------------------------------------------------------

// Optional on the wire, filled with `value` when the model omits it.
// Descriptions go on the inner schema so they survive into the JSON Schema.
function withDefault<S extends Schema.Top>(
  schema: S,
  value: S["Rebuild"]["Type"],
  description: string,
) {
  return Schema.withDecodingDefaultTypeKey<S["Rebuild"]>(Effect.succeed(value))(
    schema.annotate({ description }),
  );
}

function optionalField<S extends Schema.Top>(schema: S, description: string) {
  return Schema.optionalKey(schema.annotate({ description }));
}

const NoInput = Schema.Struct({});

const LifecycleInput = Schema.Struct({
  installModules: withDefault(
    Schema.Boolean,
    false,
    "Run node-modules install for all apps before starting",
  ),
  wait: withDefault(
    Schema.Boolean,
    true,
    "Wait until services are ready before returning",
  ),
});

const ModeInput = (
  fixDescription: string,
) =>
  Schema.Struct({
    mode: withDefault(Schema.Literals(["check", "fix"]), "check", fixDescription),
    files: optionalField(
      Schema.Array(Schema.String),
      "Optional app-relative file paths to check instead of the whole project (e.g. ['components/AppFoo.vue']). Omit to check everything.",
    ),
  });

const FilesInput = Schema.Struct({
  files: optionalField(
    Schema.Array(Schema.String),
    "Optional app-relative file paths to check instead of the whole project (e.g. ['components/AppFoo.vue']). Omit to check everything.",
  ),
});

const text = (content: string) => ({ content });

// ---------------------------------------------------------------------------
// Plugin
// ---------------------------------------------------------------------------

export default Plugin.define({
  id: "haya",
  async setup(ctx) {
    await ctx.tool.transform((editor) => {
      // -- Stack lifecycle -------------------------------------------------

      editor.add({
        name: "haya_up",
        description: `Start the Haya stack (docker compose up -d). Set installModules=true to run the non-interactive npm install for all Nuxt apps + shared lib first. Waits for services to be ready unless wait=false. Never run bare \`make up\` (it prompts interactively). ${SCOPE_NOTE}`,
        input: LifecycleInput,
        execute: async (input, context) => {
          const parts: string[] = [];
          if (input.installModules) {
            parts.push(
              await run("make", ["npm", "ARGS=--install-all"], {
                timeout: LONG_TIMEOUT,
              }),
            );
          }
          parts.push(await run("make", ["dcup"], { timeout: LONG_TIMEOUT }));
          if (input.wait) {
            parts.push(await waitHealthy(WAIT_SERVICES, 300_000, context.signal));
          }
          return text(parts.join("\n---\n"));
        },
      });

      editor.add({
        name: "haya_down",
        description: `Stop the Haya stack (docker compose down --remove-orphans). ${SCOPE_NOTE}`,
        input: NoInput,
        execute: async () =>
          text(await run("make", ["down"], { timeout: CHECK_TIMEOUT })),
      });

      editor.add({
        name: "haya_restart",
        description: `Restart the Haya stack (down, then up). Set installModules=true to also reinstall all node modules non-interactively first. Waits for services to be ready unless wait=false. ${SCOPE_NOTE}`,
        input: LifecycleInput,
        execute: async (input, context) => {
          const parts = [await run("make", ["down"], { timeout: CHECK_TIMEOUT })];
          if (input.installModules) {
            parts.push(
              await run("make", ["npm", "ARGS=--install-all"], {
                timeout: LONG_TIMEOUT,
              }),
            );
          }
          parts.push(await run("make", ["dcup"], { timeout: LONG_TIMEOUT }));
          if (input.wait) {
            parts.push(await waitHealthy(WAIT_SERVICES, 300_000, context.signal));
          }
          return text(parts.join("\n---\n"));
        },
      });

      editor.add({
        name: "haya_build",
        description: `Build Haya docker images (all, or a single service). ${SCOPE_NOTE}`,
        input: Schema.Struct({
          service: withDefault(
            Schema.Literals(["all", "api", "create", "collect", "collaborate"]),
            "all",
            "Which service image to build",
          ),
        }),
        execute: async (input) => {
          if (input.service === "all") {
            return text(await run("make", ["build"], { timeout: LONG_TIMEOUT }));
          }
          const base = await composeArgs();
          return text(
            await run("docker", [...base, "build", `haysto-${input.service}`], {
              timeout: LONG_TIMEOUT,
            }),
          );
        },
      });

      const npmInstalls = {
        create: { service: "haysto-create", cmd: ["npm", "install"] },
        collect: { service: "haysto-collect", cmd: ["npm", "install"] },
        collaborate: { service: "haysto-collaborate", cmd: ["npm", "install"] },
        shared: {
          service: "haysto-create",
          cmd: ["sh", "-c", "cd lib/js/haysto-v2-lib_shared && npm install"],
        },
      } as const;

      editor.add({
        name: "haya_npm",
        description: `Install node modules for Nuxt apps (non-interactive, inside docker). Scope 'all' installs create, collect, collaborate, then shared lib last (order matters). ${SCOPE_NOTE}`,
        input: Schema.Struct({
          scope: withDefault(
            Schema.Literals(["all", "create", "collect", "collaborate", "shared"]),
            "all",
            "Which project to install node modules for",
          ),
        }),
        execute: async (input) => {
          const order =
            input.scope === "all"
              ? (["create", "collect", "collaborate", "shared"] as const)
              : [input.scope];
          const outputs: string[] = [];
          for (const key of order) {
            const { service, cmd } = npmInstalls[key];
            outputs.push(
              `## ${key}\n` +
                (await composeRun(service, [...cmd], { timeout: LONG_TIMEOUT })),
            );
          }
          return text(outputs.join("\n---\n"));
        },
      });

      editor.add({
        name: "haya_exec_api",
        description: `Run a non-interactive shell command inside the haysto-api container (e.g. 'php artisan about', 'php -v', 'ls storage/logs'). Requires the stack to be up (haya_up). Local env only. Never use for interactive shells. ${SCOPE_NOTE}`,
        input: Schema.Struct({
          command: Schema.String.pipe(
            Schema.annotate({ description: "Shell command to run inside haysto-api" }),
          ),
          timeoutMs: optionalField(Schema.Int, "Timeout in ms (default 120000)"),
        }),
        execute: async (input) =>
          text(
            await composeExec("haysto-api", ["sh", "-c", input.command], {
              timeout: input.timeoutMs ?? 120_000,
            }),
          ),
      });

      // -- Observability (read-only) + readiness ---------------------------

      editor.add({
        name: "haya_status",
        description: `Show Haya container status (service, state, published ports). Read-only. Call this before exec-based tools to check the stack is up. ${SCOPE_NOTE}`,
        input: NoInput,
        execute: async () => {
          const containers = await composePs();
          if (!containers.length)
            return text("No containers found (stack may be down — see haya_up).");
          return text(
            containers
              .map((container) => {
                const svc = container.Service ?? container.Name ?? "?";
                const state = container.State ?? container.Status ?? "?";
                const ports = formatPublishers(container.Publishers);
                return `${svc}: ${state}${ports ? ` (${ports})` : ""}`;
              })
              .join("\n"),
          );
        },
      });

      editor.add({
        name: "haya_logs",
        description: `Read recent logs for a Haya service. Read-only. Use tail to limit lines and contains to filter (e.g. 'ERROR'). ${SCOPE_NOTE}`,
        input: Schema.Struct({
          service: Schema.Literals([
            "api",
            "create",
            "collect",
            "collaborate",
            "nginx",
            "mysql",
            "supervisor",
          ]).pipe(Schema.annotate({ description: "Which service's logs to read" })),
          tail: withDefault(
            Schema.Int,
            100,
            "Number of recent lines (default 100, max 2000)",
          ),
          contains: optionalField(
            Schema.String,
            "Only show lines containing this substring",
          ),
        }),
        execute: async (input) => {
          const base = await composeArgs();
          const out = await run(
            "docker",
            [
              ...base,
              "logs",
              "--no-color",
              "--tail",
              String(Math.max(1, Math.min(input.tail, 2000))),
              HAYA_SERVICES[input.service],
            ],
            { timeout: 60_000 },
          );
          const clean = out.replace(/\u001b\[[0-9;]*m/g, "");
          if (!input.contains) return text(clean);
          const needle = input.contains.toLowerCase();
          const hits = clean
            .split("\n")
            .filter((line) => line.toLowerCase().includes(needle));
          return text(hits.length ? tail(hits.join("\n")) : "(no matching lines)");
        },
      });

      editor.add({
        name: "haya_wait_healthy",
        description: `Wait until Haya services are running and Nuxt dev servers answer HTTP. Polls every 5s until timeout. Use after haya_up/haya_restart before API-dependent work. ${SCOPE_NOTE}`,
        input: Schema.Struct({
          services: withDefault(
            Schema.Array(Schema.Literals(WAIT_SERVICES)),
            WAIT_SERVICES,
            "Which services to wait for",
          ),
          timeoutMs: withDefault(
            Schema.Int,
            300_000,
            "Max wait in ms (default 300000)",
          ),
        }),
        execute: async (input, context) =>
          text(await waitHealthy(input.services, input.timeoutMs, context.signal)),
      });

      // -- haysto-v2-create / haysto-v2-collect ----------------------------

      const wrapperApps = [
        { key: "create", dir: CREATE_DIR },
        { key: "collect", dir: COLLECT_DIR },
      ] as const;

      for (const app of wrapperApps) {
        editor.add({
          name: `haya_${app.key}_lint`,
          description: `Run eslint on haysto-v2-${app.key} inside docker. Mode check reports errors, fix auto-fixes them. Pass files to check only those paths. ${SCOPE_NOTE}`,
          input: ModeInput("check or auto-fix"),
          execute: async (input) =>
            text(
              await viaWrapper(
                app.dir,
                "scripts/eslint.mjs",
                input.mode === "fix" ? ["--fix"] : [],
                input.files,
              ),
            ),
        });

        editor.add({
          name: `haya_${app.key}_format`,
          description: `Run prettier on haysto-v2-${app.key} inside docker. Mode check reports diffs, fix rewrites files. Pass files to check only those paths. ${SCOPE_NOTE}`,
          input: ModeInput("check or write fixes"),
          execute: async (input) =>
            text(
              await viaWrapper(
                app.dir,
                "scripts/prettier.mjs",
                input.mode === "fix" ? ["--write"] : [],
                input.files,
              ),
            ),
        });

        editor.add({
          name: `haya_${app.key}_baseline`,
          description: `TypeScript baseline check for haysto-v2-${app.key} inside docker: fails only on new errors vs the baseline. The baseline file is maintainer-managed — fix the code, never rewrite the baseline. ${SCOPE_NOTE}`,
          input: FilesInput,
          execute: async (input) =>
            text(
              await viaWrapper(
                app.dir,
                "scripts/typescript-baseline-check.mjs",
                [],
                input.files,
              ),
            ),
        });
      }

      // -- haysto-v2-collaborate (npm scripts inside the container) --------

      editor.add({
        name: "haya_collaborate_lint",
        description: `Run eslint on haysto-v2-collaborate inside docker. Mode check reports, fix auto-fixes. Pass files to lint only those paths. ${SCOPE_NOTE}`,
        input: ModeInput("check or auto-fix"),
        execute: async (input) => {
          const targets = sanitizeFiles(input.files);
          if (targets?.length) {
            return text(
              await composeRun(
                "haysto-collaborate",
                ["npx", "eslint", ...(input.mode === "fix" ? ["--fix"] : []), ...targets],
                { timeout: LONG_TIMEOUT },
              ),
            );
          }
          if (input.files?.length)
            return text("(no valid files to check — use app-relative paths)");
          return text(
            await composeRun(
              "haysto-collaborate",
              ["npm", "run", input.mode === "fix" ? "lint:fix" : "lint", "--silent"],
              { timeout: LONG_TIMEOUT },
            ),
          );
        },
      });

      editor.add({
        name: "haya_collaborate_format",
        description: `Run prettier on haysto-v2-collaborate inside docker. Mode check reports, fix rewrites. Pass files to check only those paths. ${SCOPE_NOTE}`,
        input: ModeInput("check or write fixes"),
        execute: async (input) => {
          const targets = sanitizeFiles(input.files);
          if (targets?.length) {
            return text(
              await composeRun(
                "haysto-collaborate",
                [
                  "npx",
                  "prettier",
                  input.mode === "fix" ? "--write" : "--check",
                  "--log-level",
                  "warn",
                  ...targets,
                ],
                { timeout: LONG_TIMEOUT },
              ),
            );
          }
          if (input.files?.length)
            return text("(no valid files to check — use app-relative paths)");
          return text(
            await composeRun(
              "haysto-collaborate",
              ["npm", "run", input.mode === "fix" ? "format:fix" : "format", "--silent"],
              { timeout: LONG_TIMEOUT },
            ),
          );
        },
      });

      editor.add({
        name: "haya_collaborate_typecheck",
        description: `Typecheck haysto-v2-collaborate inside docker. check = full vue-tsc, baseline = fail only on new errors vs baseline. The baseline file is maintainer-managed — fix the code, never rewrite the baseline. ${SCOPE_NOTE}`,
        input: Schema.Struct({
          mode: withDefault(
            Schema.Literals(["check", "baseline"]),
            "baseline",
            "typecheck mode",
          ),
        }),
        execute: async (input) =>
          text(
            await composeRun(
              "haysto-collaborate",
              [
                "npm",
                "run",
                input.mode === "check" ? "typecheck" : "typecheck:baseline",
                "--silent",
              ],
              { timeout: LONG_TIMEOUT },
            ),
          ),
      });

      // -- PHP / API-only --------------------------------------------------

      editor.add({
        name: "haya_phpstan",
        description: `Run PHPStan analysis inside haysto-api. Requires the stack to be up. Optional path limits analysis (e.g. 'app/Services'). ${SCOPE_NOTE}`,
        input: Schema.Struct({
          path: optionalField(
            Schema.String,
            "Sub-path to analyse, relative to haysto-v2-api",
          ),
        }),
        execute: async (input) => {
          const target = input.path ? [`dir=${input.path}`] : [];
          return text(
            await run("make", ["phpstan", ...target], { timeout: LONG_TIMEOUT }),
          );
        },
      });

      editor.add({
        name: "haya_phpstan_baseline",
        description: `Regenerate the PHPStan baseline inside haysto-api (make baseline). Requires the stack to be up. Use sparingly — it rewrites baselines. ${SCOPE_NOTE}`,
        input: NoInput,
        execute: async () =>
          text(await run("make", ["baseline"], { timeout: LONG_TIMEOUT })),
      });

      editor.add({
        name: "haya_migrate",
        description: `Run database migrations inside haysto-api (make migrate). Requires the stack to be up. ${SCOPE_NOTE}`,
        input: NoInput,
        execute: async () =>
          text(await run("make", ["migrate"], { timeout: CHECK_TIMEOUT })),
      });

      const seedTargets = {
        cases: "cases",
        case: "case",
        "deployment-safe": "seed_deployment_safe",
        "fact-find": "seed_fact_find",
        permissions: "update_permissions",
      } as const;

      editor.add({
        name: "haya_api_seed",
        description: `Run a non-destructive API seeder: cases (bulk dev cases), case (single dev case), deployment-safe, fact-find, or permissions reseed. Requires the stack to be up. ${SCOPE_NOTE}`,
        input: Schema.Struct({
          target: Schema.Literals([
            "cases",
            "case",
            "deployment-safe",
            "fact-find",
            "permissions",
          ]).pipe(Schema.annotate({ description: "Which seeder to run" })),
        }),
        execute: async (input) =>
          text(
            await run("make", [seedTargets[input.target]], {
              timeout: LONG_TIMEOUT,
            }),
          ),
      });
    });
  },
});
