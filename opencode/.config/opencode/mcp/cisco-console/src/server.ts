import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { mkdir, writeFile } from 'node:fs/promises'
import { homedir } from 'node:os'
import { join } from 'node:path'
import { z } from 'zod'
import { RouterConsole, type CommandResult } from './console.ts'

const MAX_OUTPUT_CHARS = 30_000

const INSTRUCTIONS = `Drives the serial console of a live Cisco IOS router (the home internet gateway) in privileged EXEC mode.
- The router is the user's internet connection. Only change its configuration when the user has asked for that specific change.
- Before a change: explain it, and take a backup with router_backup (never relay the config text through the conversation). After a change: verify connectivity (ping 1.1.1.1) before saving with 'write memory'. Never save unverified changes.
- Avoid very long commands (show tech-support, debug). Disable any debug output immediately ('undebug all').
- If a result says awaitingInput, the router asked a question such as [confirm]. Answer it deliberately with router_exec, never blindly.
- Only one program can hold the serial port. Use router_disconnect to release it for 'screen'.`

const router = new RouterConsole()

const REPO_DIR = process.env.CISCO_REPO_DIR ?? join(homedir(), 'code', 'cisco-network-config')
const BACKUP_FILE = process.env.CISCO_BACKUP_FILE ?? join(REPO_DIR, 'working-config-backup.txt')
const BACKUP_HISTORY_DIR = process.env.CISCO_BACKUP_DIR ?? join(REPO_DIR, 'backups')

function timestamp(date: Date): string {
  const pad = (value: number): string => String(value).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
}

async function takeBackup(saveToFlash: boolean, reason: string): Promise<string> {
  const { config, consoleLogs } = await router.captureRunningConfig()
  const now = new Date()
  const stamp = timestamp(now)
  const hostname = config.match(/^hostname (\S+)/m)?.[1] ?? 'unknown'
  const version = config.match(/^version (\S+)/m)?.[1] ?? 'unknown'

  const diff = await router.run('show archive config differences nvram:startup-config system:running-config', 60_000)
  const matchesStartup = diff.output.includes('No changes were found')

  const header = [
    '! ============================================================',
    `! ${hostname} Cisco C897VA-K9 IOS ${version} - CONFIG BACKUP`,
    `! Captured ${now.toISOString()} from the running config${reason ? ` (${reason})` : ''}.`,
    `! Running config ${matchesStartup ? 'is identical to' : 'DIFFERS from (has unsaved changes vs)'} the startup config.`,
    '! Unredacted. Secrets are Cisco hashes (type 9) or reversible type 7 (PPPoE). Do not share this file.',
    "! Restore: paste into 'configure terminal' on the console in chunks, then 'write memory'. Test first.",
    '! ============================================================',
    '',
    '',
  ].join('\n')
  const content = `${header}${config}\n`

  await mkdir(BACKUP_HISTORY_DIR, { recursive: true })
  const historyFile = join(BACKUP_HISTORY_DIR, `config-${stamp}.txt`)
  await writeFile(BACKUP_FILE, content)
  await writeFile(historyFile, content)

  const summary = [
    `Backup written (${config.split('\n').length} lines, ${content.length} bytes).`,
    `Latest:  ${BACKUP_FILE}`,
    `History: ${historyFile}`,
    `Running config ${matchesStartup ? 'matches' : 'DIFFERS from'} the startup config.`,
  ]
  if (consoleLogs.length > 0) summary.push(`Note: ${consoleLogs.length} console log line(s) arrived during capture and were removed.`)

  if (saveToFlash) {
    const flashName = `backup-${stamp}.cfg`
    let copy = await router.run(`copy system:running-config flash:${flashName}`, 60_000)
    // IOS asks to confirm the destination name even when given; accept only our own name
    if (copy.awaitingInput && copy.prompt.startsWith('Destination filename') && copy.prompt.includes(flashName)) {
      copy = await router.sendKey('enter', 60_000)
    }
    if (copy.awaitingInput || copy.timedOut || copy.output.includes('%') || !copy.output.includes('bytes copied')) {
      summary.push(`Flash copy FAILED or needs attention: ${copy.output}\n[prompt: ${copy.prompt}]\nIf the router is still showing a question, resolve it (router_send_key ctrl-c) before sending any other command, or that command will be taken as the answer.`)
    } else {
      const listing = await router.run(`dir flash:${flashName}`, 30_000)
      const confirmed = listing.output.includes(flashName)
      summary.push(
        confirmed
          ? `Flash copy: flash:${flashName}. Roll back with 'configure replace flash:${flashName}' (ask the user first).`
          : `Flash copy could not be confirmed: ${listing.output}`,
      )
    }
  }
  return summary.join('\n')
}

function formatResult(result: CommandResult): string {
  const output =
    result.output.length > MAX_OUTPUT_CHARS
      ? `${result.output.slice(0, MAX_OUTPUT_CHARS)}\n[output truncated at ${MAX_OUTPUT_CHARS} characters]`
      : result.output
  const notes: string[] = []
  if (result.timedOut) {
    notes.push('TIMED OUT: the command may still be running. Use router_read to collect more, or router_send_key with "abort".')
  }
  if (result.awaitingInput) notes.push('AWAITING INPUT: the router is asking a question, see the prompt below.')
  if (result.consoleLogs.length > 0) {
    notes.push(
      `CONSOLE LOGS received while the command ran (removed from the output above; they may have disturbed the typed command, so verify it took effect):\n${result.consoleLogs.join('\n')}`,
    )
  }
  return [output, ...notes, `[prompt: ${result.prompt} | mode: ${result.mode}]`].filter(Boolean).join('\n')
}

function textResponse(text: string, isError = false) {
  return { content: [{ type: 'text' as const, text }], isError }
}

async function guarded(action: () => Promise<string>) {
  try {
    return textResponse(await action())
  } catch (error) {
    return textResponse(error instanceof Error ? error.message : String(error), true)
  }
}

const timeoutSeconds = z
  .number()
  .int()
  .min(1)
  .max(900)
  .default(30)
  .describe('How long to wait for the router prompt to come back, in seconds')

const server = new McpServer({ name: 'cisco-console', version: '1.0.0' }, { instructions: INSTRUCTIONS })

server.registerTool(
  'router_status',
  {
    description:
      'Open the serial console if needed, log in and enable, and report the current prompt and mode (user, privileged or config).',
  },
  () => guarded(async () => `Port ${router.portPath}\n${formatResult(await router.status())}`),
)

server.registerTool(
  'router_exec',
  {
    description:
      'Run one IOS command or answer one prompt on the router console and return its output. Works in any mode, so it can also run config commands one at a time. Use "| include" / "| begin" instead of "| head" / "| tail".',
    inputSchema: {
      command: z.string().describe('The exact line to type, without a trailing newline'),
      timeoutSeconds,
    },
  },
  ({ command, timeoutSeconds: seconds }) =>
    guarded(async () => formatResult(await router.run(command, seconds * 1000))),
)

server.registerTool(
  'router_config',
  {
    description:
      'Enter configuration mode, apply a list of config commands in order, then leave config mode. Stops at the first IOS error (lines beginning with %) or unexpected question. Does NOT save to startup-config; run "write memory" separately after verifying.',
    inputSchema: {
      commands: z.array(z.string()).min(1).describe('Config commands in order, including sub-mode entries such as "interface Vlan10"'),
      timeoutSeconds: timeoutSeconds.describe('Per-command wait for the router prompt, in seconds'),
    },
  },
  ({ commands, timeoutSeconds: seconds }) =>
    guarded(async () => {
      const { results, stoppedEarly } = await router.runConfig(commands, seconds * 1000)
      const lines = results.map(({ command, result }) => {
        const output = result.output ? `\n${result.output}` : ''
        return `${result.prompt} ${command}${output}`
      })
      const final = results.at(-1)?.result
      const footer = stoppedEarly
        ? 'STOPPED EARLY: a command failed or the router asked a question. Remaining commands were not applied. The console may still be in config mode.'
        : 'All commands applied (not saved to startup-config).'
      return [...lines, footer, final ? `[prompt: ${final.prompt} | mode: ${final.mode}]` : ''].join('\n')
    }),
)

server.registerTool(
  'router_backup',
  {
    description:
      'Capture the full running config and write it to the repo (latest file plus a timestamped copy in backups/), verified complete, and report whether it matches the startup config. The config text is NOT returned. Optionally also copy it to router flash for on-device rollback. Run before and after every config change.',
    inputSchema: {
      reason: z.string().default('').describe('Short note for the backup header, e.g. "before logging change"'),
      saveToFlash: z.boolean().default(false).describe('Also copy running-config to flash:backup-<timestamp>.cfg on the router'),
    },
  },
  ({ reason, saveToFlash }) => guarded(() => takeBackup(saveToFlash, reason)),
)

server.registerTool(
  'router_read',
  {
    description: 'Collect output that arrived after an earlier command timed out, waiting for the prompt to return.',
    inputSchema: { timeoutSeconds },
  },
  ({ timeoutSeconds: seconds }) => guarded(async () => formatResult(await router.readMore(seconds * 1000))),
)

server.registerTool(
  'router_send_key',
  {
    description:
      'Send a single control key: "abort" (Ctrl+Shift+6, stops ping/traceroute), "ctrl-c", "ctrl-z" (leaves config mode), "enter" or "space".',
    inputSchema: {
      key: z.enum(['abort', 'ctrl-c', 'ctrl-z', 'enter', 'space']),
      timeoutSeconds: timeoutSeconds.default(10),
    },
  },
  ({ key, timeoutSeconds: seconds }) => guarded(async () => formatResult(await router.sendKey(key, seconds * 1000))),
)

server.registerTool(
  'router_disconnect',
  {
    description: 'Close the serial port so another program (for example screen) can use the console. The next tool call reconnects.',
  },
  () =>
    guarded(async () => {
      await router.disconnect()
      return 'Serial port released.'
    }),
)

async function shutdown(): Promise<void> {
  await router.disconnect().catch(() => undefined)
  process.exit(0)
}
process.on('SIGINT', () => void shutdown())
process.on('SIGTERM', () => void shutdown())
process.stdin.on('close', () => void shutdown())

await server.connect(new StdioServerTransport())
