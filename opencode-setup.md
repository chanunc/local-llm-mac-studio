# OpenCode Setup: MacBook / WSL → Mac Studio LLM Server

OpenCode connects **directly** to the oMLX server's OpenAI-compatible endpoint.

## Architecture

```
MacBook or WSL Linux                      Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────┐                   ┌──────────────────────────────────┐
│ OpenCode            │                   │ oMLX server (port 8000)         │
│   openai-compatible │───── LAN ────────>│   Qwen3-Coder-Next-4bit         │
│   direct connection │                   │   /v1/chat/completions          │
└─────────────────────┘                   └──────────────────────────────────┘
```

## Installation

**Important**: Use `anomalyco/tap/opencode` (actively maintained).

```bash
# macOS / Linux (Homebrew)
brew install anomalyco/tap/opencode
```

Verify: `opencode --version`

## WSL-Specific: Fix Routing

WSL2 may route LAN traffic through the wrong interface. If `eth2` is on `192.168.31.x`, add the route:

```bash
sudo ip route add 192.168.31.0/24 dev eth2
```

Verify connectivity:
```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool
```

### Make Route Persistent

WSL2 loses `ip route` changes on restart. Add to `~/.bashrc` or `~/.zshrc`:

```bash
if ! ip route | grep -q "192.168.31.0/24"; then
  sudo ip route add 192.168.31.0/24 dev eth2 2>/dev/null
fi
```

Allow passwordless sudo for this via `sudo visudo`:
```
%sudo ALL=(ALL) NOPASSWD: /sbin/ip route add 192.168.31.0/24 dev eth2
```

## Configuration

Copy config from this repo, or create manually:

```bash
mkdir -p ~/.config/opencode
cp configs/opencode.json ~/.config/opencode/opencode.json
```

Global config at `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "macstudio": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://<MAC_STUDIO_IP>:8000/v1",
        "apiKey": "<YOUR_API_KEY>",
        "timeout": 600000
      },
      "models": {
        "mlx-community/Qwen3-Coder-Next-4bit": {
          "name": "Qwen3 Coder (Mac Studio)",
          "limit": {
            "context": 16000,
            "output": 4096
          }
        }
      }
    }
  },
  "model": "macstudio/mlx-community/Qwen3-Coder-Next-4bit",
  "small_model": "macstudio/mlx-community/Qwen3-Coder-Next-4bit"
}
```

### Shell Alias

Add to `~/.zshrc` or `~/.bashrc`:

```bash
alias oc='opencode'
```

## Testing

1. **Connectivity check**:
   ```bash
   curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
     -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool
   ```

2. **Launch interactive TUI**:
   ```bash
   opencode
   ```
   Send "Hello" and verify you get a response.

3. **One-shot test**:
   ```bash
   opencode -p "Write a Python hello world"
   ```

4. **Tool use test**: Create a test file, then ask OpenCode to read it.

## Troubleshooting

### `Error: agent coder not found`

You have the old archived `opencode-ai/opencode` installed (version `0.0.x`). Switch to the `anomalyco/tap` version:
```bash
brew uninstall opencode
brew install anomalyco/tap/opencode
```

### WSL: curl to Mac Studio times out

Check routing — traffic may be going through the wrong interface:
```bash
ip route get <MAC_STUDIO_IP>
# Should show: dev eth2
```

If not, add the route (see WSL-Specific section above).

### Can't connect to Mac Studio

- Verify the server is running: `curl -s http://<MAC_STUDIO_IP>:8000/v1/models -H "Authorization: Bearer <YOUR_API_KEY>"`
- Restart oMLX:
  ```bash
  ssh macstudio "brew services restart omlx"
  ```

### Slow or hanging responses

- The 600000ms (10 min) timeout in config should handle long generations
- Check Mac Studio memory pressure: `ssh macstudio "memory_pressure"`
- Reduce `context` limit in config if model runs out of memory

### Context limit errors

- Qwen3-Coder-Next-4bit supports up to 32K context but large contexts use more memory
- Client context is set to 16K by default (conservative for stability)
- Increase `limit.context` in config up to 32000 if you need more but monitor memory

### Server reliability

oMLX is installed via Homebrew on the Mac Studio (`brew install omlx`). It natively serves both OpenAI and Anthropic API formats on a single port.

`brew services start omlx` auto-restarts on crash natively. Check status: `ssh macstudio 'brew services info omlx'`.

Logs: `/opt/homebrew/var/log/omlx.log` (service) and `~/.omlx/logs/server.log` (application).

Upgrade with: `ssh macstudio "/opt/homebrew/bin/brew upgrade omlx"`

## Changing the Model

1. Load the new model on Mac Studio (see `summary.md` "Changing the LLM Model")
2. Update `opencode.json`:
   - Change model ID in `models` key and in `model`/`small_model` fields
   - Adjust `context` and `output` limits for the new model
3. Restart OpenCode

## Comparison with Claude Code Setup

| | Claude Code | OpenCode |
|---|---|---|
| API format | Anthropic (native) | OpenAI (native) |
| Proxy needed | No | No |
| Config file | `~/.claude/macstudio-settings.json` | `~/.config/opencode/opencode.json` |
| Launch command | `claude-local` | `opencode` / `oc` |
