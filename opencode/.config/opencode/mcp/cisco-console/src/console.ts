import { appendFile, mkdir, readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { SerialPort } from 'serialport'

const DEFAULT_PORT = '/dev/cu.usbserial-AB9DDNJP'
const DEFAULT_ENV_FILE = join(homedir(), 'code', 'cisco-network-config', '.env')
const TRANSCRIPT_FILE = join(dirname(fileURLToPath(import.meta.url)), '..', 'logs', 'transcript.log')
const BAUD_RATE = 9600
const SETTLE_MS = 250
const LOGIN_TIMEOUT_MS = 15_000

const EXEC_PROMPT = /^[\w.-]+(?:\([^)\s]+\))?[#>]$/
const QUESTION_PROMPT =
  /(?:\[confirm\]|\[y(?:es)?\/n(?:o)?\]:?|\(y\/n\)\??|\(yes\/no\)\??|\[[^\]\n]*\]\??|[Pp]assword:|Username:)\s*$/
const SYSLOG_LINE = /^[*.]?[A-Z][a-z]{2} +\d{1,2} \d\d:\d\d:\d\d(?:\.\d+)?: %/
const MORE_PROMPT = /--More--\s*$/

export type RouterMode = 'user' | 'privileged' | 'config' | 'unknown'

export interface CommandResult {
  output: string
  prompt: string
  mode: RouterMode
  timedOut: boolean
  awaitingInput: boolean
  /** Syslog messages the router pushed onto the console while the command ran. */
  consoleLogs: string[]
}

interface Credentials {
  username: string
  password: string
  enablePassword: string
}

export type ControlKey = 'enter' | 'space' | 'ctrl-c' | 'ctrl-z' | 'abort'

const CONTROL_KEYS: Record<ControlKey, string> = {
  enter: '\r',
  space: ' ',
  'ctrl-c': '\x03',
  'ctrl-z': '\x1a',
  // Ctrl+Shift+6, the IOS escape sequence that aborts ping, traceroute and similar
  abort: '\x1e',
}

function cleanTerminalText(raw: string): string {
  let line = ''
  const lines: string[] = []
  const withoutAnsi = raw.replace(/\x1b\[[0-9;?]*[A-Za-z]/g, '')
  for (const char of withoutAnsi) {
    if (char === '\b') {
      line = line.slice(0, -1)
    } else if (char === '\n') {
      lines.push(line)
      line = ''
    } else if (char !== '\r' && char !== '\0') {
      line += char
    }
  }
  lines.push(line)
  return lines.join('\n')
}

function lastLine(text: string): string {
  return text.slice(text.lastIndexOf('\n') + 1).trim()
}

function modeFromPrompt(prompt: string): RouterMode {
  if (!EXEC_PROMPT.test(prompt)) return 'unknown'
  if (prompt.includes('(')) return 'config'
  return prompt.endsWith('#') ? 'privileged' : 'user'
}

async function loadCredentials(): Promise<Credentials> {
  const envFile = process.env.CISCO_ENV_FILE ?? DEFAULT_ENV_FILE
  const values = new Map<string, string>()
  for (const line of (await readFile(envFile, 'utf8')).split('\n')) {
    const separator = line.indexOf('=')
    if (separator > 0 && !line.startsWith('#')) {
      values.set(line.slice(0, separator).trim(), line.slice(separator + 1).trim())
    }
  }
  const read = (key: string): string => {
    const value = values.get(key)
    if (value === undefined) throw new Error(`${key} is missing from ${envFile}`)
    return value
  }
  return {
    username: read('ROUTER-USER_USERNAME'),
    password: read('ROUTER-USER_PASSWORD'),
    enablePassword: read('ROUTER-ENABLE_PASSWORD'),
  }
}

async function logTranscript(entry: string): Promise<void> {
  await mkdir(dirname(TRANSCRIPT_FILE), { recursive: true })
  await appendFile(TRANSCRIPT_FILE, `${new Date().toISOString()} ${entry}\n`)
}

export class RouterConsole {
  private port: SerialPort | null = null
  private buffer = ''
  private ready = false
  private dataWaiters = new Set<() => void>()
  private queue: Promise<unknown> = Promise.resolve()
  private eventLoopTick: NodeJS.Timeout | null = null

  get portPath(): string {
    return process.env.CISCO_CONSOLE_PORT ?? DEFAULT_PORT
  }

  /** Runs tasks one at a time, since the serial line can only carry one conversation. */
  private exclusive<T>(task: () => Promise<T>): Promise<T> {
    const result = this.queue.then(task, task)
    this.queue = result.catch(() => undefined)
    return result
  }

  private onData(chunk: Buffer): void {
    this.buffer += chunk.toString('latin1')
    for (const wake of [...this.dataWaiters]) wake()
  }

  private waitForData(timeoutMs: number): Promise<boolean> {
    return new Promise((resolve) => {
      const finish = (arrived: boolean): void => {
        clearTimeout(timer)
        this.dataWaiters.delete(onArrival)
        resolve(arrived)
      }
      const onArrival = (): void => finish(true)
      const timer = setTimeout(() => finish(false), timeoutMs)
      this.dataWaiters.add(onArrival)
    })
  }

  private async open(): Promise<void> {
    if (this.port?.isOpen) return
    const port = new SerialPort({ path: this.portPath, baudRate: BAUD_RATE, autoOpen: false })
    await new Promise<void>((resolve, reject) => {
      port.open((error) => (error ? reject(error) : resolve()))
    })
    port.on('data', (chunk: Buffer) => this.onData(chunk))
    port.on('close', () => {
      this.ready = false
      this.port = null
      if (this.eventLoopTick) clearInterval(this.eventLoopTick)
      this.eventLoopTick = null
    })
    // On macOS, serial reads are only delivered when the event loop is otherwise woken, which
    // delays responses by seconds. A cheap periodic tick keeps the loop turning.
    this.eventLoopTick = setInterval(() => undefined, 20)
    this.port = port
    this.buffer = ''
  }

  private write(text: string): Promise<void> {
    const port = this.port
    if (!port?.isOpen) throw new Error('Serial port is not open')
    return new Promise((resolve, reject) => {
      port.write(text, (error) => (error ? reject(error) : resolve()))
    })
  }

  private async collect(
    timeoutMs: number,
    isDone: (text: string) => boolean,
  ): Promise<{ text: string; timedOut: boolean }> {
    const deadline = Date.now() + timeoutMs
    let awaitingMoreErase = false
    for (;;) {
      const remaining = deadline - Date.now()
      const text = cleanTerminalText(this.buffer)
      if (remaining <= 0) return { text, timedOut: true }

      if (MORE_PROMPT.test(text)) {
        if (!awaitingMoreErase) {
          awaitingMoreErase = true
          await this.write(' ')
        }
        await this.waitForData(remaining)
        continue
      }
      awaitingMoreErase = false

      if (isDone(text)) {
        const moreArrived = await this.waitForData(Math.min(SETTLE_MS, remaining))
        if (!moreArrived) return { text, timedOut: false }
        continue
      }
      await this.waitForData(remaining)
    }
  }

  private isPromptText(text: string): boolean {
    const line = lastLine(text)
    return EXEC_PROMPT.test(line) || QUESTION_PROMPT.test(line)
  }

  private async login(): Promise<void> {
    const credentials = await loadCredentials()
    this.buffer = ''
    await this.write('\r')
    let sentUsername = false
    let sentPassword = false
    let sentEnable = false
    let sentEnablePassword = false
    const deadline = Date.now() + LOGIN_TIMEOUT_MS

    while (Date.now() < deadline) {
      const { text } = await this.collect(3000, (current) => this.isPromptText(current))
      const prompt = lastLine(text)
      this.buffer = ''

      if (/Username:$/.test(prompt) && !sentUsername) {
        sentUsername = true
        await this.write(`${credentials.username}\r`)
      } else if (/Password:$/.test(prompt)) {
        if (sentEnable && !sentEnablePassword) {
          sentEnablePassword = true
          await this.write(`${credentials.enablePassword}\r`)
        } else if (!sentPassword) {
          sentPassword = true
          await this.write(`${credentials.password}\r`)
        } else {
          throw new Error('Router rejected the credentials from the env file')
        }
      } else if (modeFromPrompt(prompt) === 'user' && !sentEnable) {
        sentEnable = true
        await this.write('enable\r')
      } else if (modeFromPrompt(prompt) === 'config') {
        await this.write('end\r')
      } else if (modeFromPrompt(prompt) === 'privileged') {
        for (const setting of ['terminal length 0', 'terminal width 0']) {
          this.buffer = ''
          await this.write(`${setting}\r`)
          await this.collect(5000, (current) => this.isPromptText(current))
        }
        while (await this.waitForData(SETTLE_MS)) continue
        this.buffer = ''
        this.ready = true
        void logTranscript('[login] console session established')
        return
      } else {
        await this.write('\r')
      }
    }
    throw new Error('Timed out logging in to the router console')
  }

  private async ensureReady(): Promise<void> {
    await this.open()
    if (!this.ready) await this.login()
  }

  /** Sends a line, logging in again first if the router's idle timeout has dropped the session. */
  private async sendLine(command: string, timeoutMs: number): Promise<CommandResult> {
    const result = await this.sendLineOnce(command, timeoutMs)
    const loggedOut = result.mode === 'user' || /(?:Username|Password):$/.test(result.prompt)
    if (!loggedOut || command.trim() === '') return result
    void logTranscript('[relogin] session had dropped to user mode or a login prompt')
    this.ready = false
    await this.login()
    return this.sendLineOnce(command, timeoutMs)
  }

  private async sendLineOnce(command: string, timeoutMs: number): Promise<CommandResult> {
    this.buffer = ''
    void logTranscript(`> ${command}`)
    await this.write(`${command}\r`)
    const { text, timedOut } = await this.collect(timeoutMs, (current) => this.isPromptText(current))
    this.buffer = ''
    return this.toResult(text, timedOut, command)
  }

  private toResult(text: string, timedOut: boolean, command?: string): CommandResult {
    const lines = text.split('\n')
    const prompt = lines.at(-1)?.trim() ?? ''
    const body = lines.slice(0, -1)
    const trimmedCommand = command?.trim()
    if (trimmedCommand && body.length > 0 && body[0]?.includes(trimmedCommand.slice(0, 20))) {
      body.shift()
    }
    const awaitingInput = !timedOut && QUESTION_PROMPT.test(prompt) && !EXEC_PROMPT.test(prompt)
    const showsLogs = trimmedCommand?.startsWith('show log') ?? false
    const consoleLogs = showsLogs ? [] : body.filter((line) => SYSLOG_LINE.test(line)).map((line) => line.trim())
    const kept = showsLogs ? body : body.filter((line) => !SYSLOG_LINE.test(line))
    const output = kept.map((line) => line.trimEnd()).join('\n').trim()
    void logTranscript(`< ${output.slice(0, 2000)}${output.length > 2000 ? ' [truncated in log]' : ''}\n${prompt}`)
    return { output, prompt, mode: modeFromPrompt(prompt), timedOut, awaitingInput, consoleLogs }
  }

  status(): Promise<CommandResult> {
    return this.exclusive(async () => {
      await this.ensureReady()
      return this.sendLine('show clock', 5000)
    })
  }

  run(command: string, timeoutMs: number): Promise<CommandResult> {
    return this.exclusive(async () => {
      await this.ensureReady()
      return this.sendLine(command, timeoutMs)
    })
  }

  /**
   * Enters configuration mode, applies the commands in order and leaves it again.
   * Stops at the first IOS error (a line starting with %) or unexpected prompt.
   */
  runConfig(
    commands: string[],
    timeoutMs: number,
  ): Promise<{ results: Array<{ command: string; result: CommandResult }>; stoppedEarly: boolean }> {
    return this.exclusive(async () => {
      await this.ensureReady()
      const results: Array<{ command: string; result: CommandResult }> = []
      const enter = await this.sendLine('configure terminal', timeoutMs)
      results.push({ command: 'configure terminal', result: enter })
      if (enter.mode !== 'config') return { results, stoppedEarly: true }

      let stoppedEarly = false
      for (const command of commands) {
        const result = await this.sendLine(command, timeoutMs)
        results.push({ command, result })
        const failed = result.output.split('\n').some((line) => line.startsWith('%'))
        if (failed || result.timedOut || result.awaitingInput) {
          stoppedEarly = true
          break
        }
      }

      const last = results.at(-1)?.result
      if (last && !last.timedOut && !last.awaitingInput) {
        const leave = await this.sendLine('end', timeoutMs)
        results.push({ command: 'end', result: leave })
      }
      return { results, stoppedEarly }
    })
  }

  /** Returns whatever has arrived since the last command, waiting for it to go quiet. */
  readMore(timeoutMs: number): Promise<CommandResult> {
    return this.exclusive(async () => {
      await this.ensureReady()
      const { text, timedOut } = await this.collect(timeoutMs, (current) => this.isPromptText(current))
      this.buffer = ''
      return this.toResult(text, timedOut)
    })
  }

  sendKey(key: ControlKey, timeoutMs: number): Promise<CommandResult> {
    return this.exclusive(async () => {
      await this.ensureReady()
      this.buffer = ''
      void logTranscript(`[key] ${key}`)
      await this.write(CONTROL_KEYS[key])
      const { text, timedOut } = await this.collect(timeoutMs, (current) => this.isPromptText(current))
      this.buffer = ''
      return this.toResult(text, timedOut)
    })
  }

  /** Captures `show running-config` and checks that it arrived complete. */
  captureRunningConfig(): Promise<{ config: string; consoleLogs: string[] }> {
    return this.exclusive(async () => {
      await this.ensureReady()
      const result = await this.sendLine('show running-config', 90_000)
      const lines = result.output.split('\n')
      const start = lines.findIndex((line) => line.startsWith('Current configuration'))
      const last = lines.at(-1)?.trim()
      if (result.timedOut || start === -1 || last !== 'end') {
        throw new Error('Running config capture was incomplete (timed out, or missing its start or end). Nothing was written.')
      }
      return { config: lines.slice(start).join('\n'), consoleLogs: result.consoleLogs }
    })
  }

  /** Releases the serial port so something else (such as screen) can use it. */
  disconnect(): Promise<void> {
    return this.exclusive(async () => {
      const port = this.port
      if (!port?.isOpen) return
      await new Promise<void>((resolve, reject) => {
        port.close((error) => (error ? reject(error) : resolve()))
      })
    })
  }
}
