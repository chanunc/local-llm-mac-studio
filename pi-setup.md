# Pi Coding Agent Setup: MacBook → Mac Studio LLM Server

Pi connects **directly** to the mlx-lm server's OpenAI-compatible endpoint — no proxy needed.

## Architecture

```
MacBook                                   Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────┐                   ┌──────────────────────────────────┐
│ Pi Coding Agent     │                   │ mlx-lm server (port 8080)       │
│   openai-completions│───── LAN ────────>│   Qwen3-Coder-Next-4bit         │
│   direct connection │                   │   /v1/chat/completions          │
└─────────────────────┘                   └──────────────────────────────────┘
```

## Installation

```bash
brew install pi-coding-agent
```

Verify: `pi --version`

## Configuration

Copy config from this repo, or create manually:

```bash
mkdir -p ~/.pi/agent
cp configs/pi-models.json ~/.pi/agent/models.json
```

Custom model config at `~/.pi/agent/models.json`:

```json
{
  "providers": {
    "macstudio": {
      "baseUrl": "http://<MAC_STUDIO_IP>:8080/v1",
      "api": "openai-completions",
      "apiKey": "not-needed",
      "compat": {
        "supportsUsageInStreaming": false,
        "maxTokensField": "max_tokens"
      },
      "models": [
        {
          "id": "mlx-community/Qwen3-Coder-Next-4bit",
          "name": "Qwen3 Coder (Mac Studio)",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 65536,
          "maxTokens": 8192,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        }
      ]
    }
  }
}
```

Key settings:
- `api: "openai-completions"` — mlx-lm speaks OpenAI Chat Completions format
- `apiKey` is required by Pi but mlx-lm ignores it
- `supportsUsageInStreaming: false` — mlx-lm may not include usage data in streaming responses
- `maxTokensField: "max_tokens"` — mlx-lm uses the older field name (not `max_completion_tokens`)
- Cost is all zeros (local model, no billing)
- The `models.json` file hot-reloads — no restart needed when editing

## Testing

1. **Connectivity check**:
   ```bash
   curl -s http://<MAC_STUDIO_IP>:8080/v1/models | python3 -m json.tool
   ```

2. **Launch Pi**:
   ```bash
   pi
   ```

3. **Select the Mac Studio model**: Use `/model` command inside Pi to switch to "Qwen3 Coder (Mac Studio)".

4. **Test prompt**: Send "Hello, write a Python hello world" and verify you get a response.

5. **Tool use test**: Ask Pi to read or create a file to verify tool calling works.

## Troubleshooting

### Can't connect to Mac Studio

- Verify the server is running: `curl http://<MAC_STUDIO_IP>:8080/v1/models`
- Check if mlx-lm is up: `ssh macstudio "launchctl list | grep mlx"`
- Restart mlx-lm:
  ```bash
  ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist"
  ```

### Model not appearing in Pi

- Check `~/.pi/agent/models.json` is valid JSON: `python3 -m json.tool ~/.pi/agent/models.json`
- The file hot-reloads, but if it doesn't appear, restart Pi

### Tool calling issues

- Qwen3-Coder-Next-4bit may not handle all tool-calling formats perfectly
- This is a model quality issue, not a configuration problem
- If tool calls fail, try simpler prompts or test with a different model

### Slow or hanging responses

- Check Mac Studio memory pressure: `ssh macstudio "memory_pressure"`
- Reduce `contextWindow` in models.json if the model runs out of memory
- The mlx-lm server has an 8192 max token default cap per request

## Changing the Model

1. Load the new model on Mac Studio (see `summary.md` "Changing the LLM Model")
2. Update `~/.pi/agent/models.json`:
   - Change `id` to the new model identifier
   - Update `name`, `contextWindow`, and `maxTokens` as appropriate
3. Pi hot-reloads `models.json` — no restart needed

## Comparison with Other Agent Setups

| | Claude Code | OpenCode | Pi |
|---|---|---|---|
| API format | Anthropic (needs proxy) | OpenAI (direct) | OpenAI (direct) |
| Proxy needed | Yes (claude-code-router) | No | No |
| Config file | `~/.claude/macstudio-settings.json` | `~/.config/opencode/opencode.json` | `~/.pi/agent/models.json` |
| Launch command | `claude-local` | `opencode` / `oc` | `pi` |
