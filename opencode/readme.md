# Ollama + OpenCode debugging cheatsheet

## 1. Check versions

ollama --version
opencode --version

## 2. Check installed models

ollama list

Detailed model information:

ollama show <model>

Useful things to check:

Parameters
Context length
Quantisation
Capabilities (completion, tools)
Template / renderer / parser

Show the Modelfile:

ollama show <model> --modelfile

## 3. Check what is actually running

ollama ps

Pay particular attention to:

PROCESSOR CONTEXT
22% CPU/78% GPU 65536

A large CPU percentage on Apple Silicon can indicate the model/context is too large for available GPU/unified memory.

## 4. Test Ollama independently of OpenCode

This is one of the most useful tests.

```
curl -s http://localhost:11434/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<model>",
    "messages": [
      {"role":"user","content":"Reply with exactly: READY"}
    ],
    "stream": false
  }'
```

If this works, Ollama/model/API are fundamentally working and the problem is probably higher up in OpenCode/integration/configuration.

Test reasoning-related behaviour separately if necessary:

```
curl -s http://localhost:11434/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<model>",
    "messages": [
      {"role":"user","content":"Reply with exactly: READY"}
    ],
    "stream": false,
    "reasoning_effort": "none"
  }'
```

## 5. Inspect OpenCode configuration

`opencode debug config`

Check which model OpenCode is actually selecting.

Don't assume the model shown in your config is the model being used.

OpenCode logs showed this was particularly useful:

model.id=devstral:latest
model.providerID=ollama

## 6. Check OpenCode's model state

cat ~/.local/state/opencode/model.json

Useful for finding:

recently selected models
duplicate-looking model entries
provider/model IDs OpenCode has remembered 7. Turn on Ollama server debugging

Quit the Ollama application, then:

OLLAMA_DEBUG=1 ollama serve

Run OpenCode against that server and watch the Ollama output.

Look for:

model loaded
runner.vram=...
runner.parallel=...
prompt_len=...
n_ctx_slot=...
prompt processing
eval time
tokens/sec

## 8. Distinguish "hung" from "slow"

This was the key discovery in our case.

If you see something like:

eval time = 30435 ms / 4 tokens
0.10 tokens/sec

OpenCode isn't necessarily broken — the model is just painfully slow.

Also look at prompt size:

task.n_tokens=7450
prompt_len=32257

A tiny direct curl test can therefore be misleading: OpenCode may send a massive system/tool/context prompt.

## 9. Check memory/context interaction

On a 24 GB Apple Silicon machine:

model size + KV cache + runtime + OpenCode prompt
↓
unified memory

A model that fits by itself may become unusable at 64K context.

For example, our Devstral investigation showed roughly:

Model: ~20 GB
Context: 65,536
Processor: 22% CPU / 78% GPU

→ severe CPU offloading and extremely low generation speed.

## 10. Don't immediately blame reasoning/tool calling

Test the raw API first.

If:

curl ... "Reply with exactly: READY"

works quickly, but OpenCode hangs, investigate:

OpenCode configuration
Actual selected model
OpenCode prompt size
Tool definitions
Context length
CPU/GPU offloading
OpenCode/Ollama integration 11. Check the actual request in Ollama logs

The most useful evidence is often:

POST "/v1/chat/completions"
prompt_len=...
n_ctx_slot=...
task.n_tokens=...
eval time=...
tokens/sec=...

This tells you whether OpenCode is:

actually reaching Ollama
sending a huge prompt
using the expected context
generating tokens
generating extremely slowly 12. General decision tree
OpenCode hangs
│
▼
Does curl → Ollama work?
│
┌────┴────┐
NO YES
│ │
▼ ▼
Ollama/ Check OpenCode
model/API config/model
problem │
▼
Check Ollama logs
│
▼
Is generation slow?
│ │
YES NO
│ │
▼ ▼
Check model + Investigate
context + tools/request
CPU/GPU split

Most useful commands to remember

```
ollama list
ollama show <model>
ollama show <model> --modelfile
ollama ps
opencode debug config
cat ~/.local/state/opencode/model.json
OLLAMA_DEBUG=1 ollama serve
```
