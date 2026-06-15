## Standalone Go branch checkout CLI

Multi git repo checkout tool.

Checks out branches across multiple repos with a single workflow:

- abort if any configured repository has uncommitted changes
- skip missing repo paths
- run `git fetch --all` per repo
- open an `fzf` branch picker for each repo
- skip on `Esc`
- run `git checkout <branch>` and then `git pull --ff-only`

Edit the repo configuration near the top of `branch-checkout/main.go`:

- `rootDir`
- `repos`

Run it from this directory:

```bash
cd branch-checkout
go run .
```

Build a local binary:

```bash
go build .
./branch-checkout
```

> Tip, add an alias to your shell config:

```bash
alias bco='{path}/branch-checkout'
# Adjust the {path} to match the location.

```

---
