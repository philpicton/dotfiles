# cisco-console MCP

MCP server that drives the serial console of a Cisco IOS router in privileged EXEC mode. It can run any command, including config changes. It is registered in `opencode.jsonc` as `cisco-console` and is **disabled by default**; enable it from `/mcps` when you want it, and disable it again afterwards. While connected it holds the serial port, so `screen` can't be used (or call `router_disconnect`).

## Tools

| Tool | Purpose |
| --- | --- |
| `router_status` | Connect, log in, enable, report prompt and mode |
| `router_backup` | Save the running config to the repo (latest plus timestamped copy), verified complete; optional copy to router flash. Returns a summary only |
| `router_exec` | Run one command (or answer one prompt) and return the output |
| `router_config` | Enter config mode, apply a list of commands, leave config mode (does not save) |
| `router_read` | Collect output after a timed-out command |
| `router_send_key` | `abort` (Ctrl+Shift+6), `ctrl-c`, `ctrl-z`, `enter`, `space` |
| `router_disconnect` | Release the serial port |

## Configuration

Environment variables (set in `opencode.jsonc`):

- `CISCO_CONSOLE_PORT`: serial device, default `/dev/cu.usbserial-AB9DDNJP`
- `CISCO_REPO_DIR`: repo for backups, default `~/code/cisco-network-config` (`CISCO_BACKUP_FILE` and `CISCO_BACKUP_DIR` override the latest file and history folder)
- `CISCO_ENV_FILE`: file containing `ROUTER-USER_USERNAME`, `ROUTER-USER_PASSWORD` and `ROUTER-ENABLE_PASSWORD`, default `~/code/cisco-network-config/.env`

Credentials are read by the server and never passed through the model or written to the transcript.

Every command and its output is appended to `logs/transcript.log` (gitignored) as an audit trail.

## Notes

- Requires Node 22.18+ (runs the TypeScript directly). Install with `npm install`; `npm run typecheck` checks types.
- On login the server runs `terminal length 0` and `terminal width 0` for the console session. These are not config changes.
- A 20 ms timer keeps the Node event loop turning while the port is open. Without it, macOS delivers serial reads seconds late.
