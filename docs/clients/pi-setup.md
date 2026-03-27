# Pi Coding Agent Setup: MacBook → Mac Studio LLM Server

Pi connects **directly** to the oMLX server's OpenAI-compatible endpoint.

## Index
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
  - [Can't connect to Mac Studio](#cant-connect-to-mac-studio)
  - [Model not appearing in Pi](#model-not-appearing-in-pi)
  - [Tool calling issues](#tool-calling-issues)
  - [422 Unprocessable Entity with reasoning models](#422-unprocessable-entity-with-reasoning-models)
  - [Slow or hanging responses](#slow-or-hanging-responses)
- [Changing the Model](#changing-the-model)
- [Comparison with Other Agent Setups](#comparison-with-other-agent-setups)

## Architecture

```
MacBook                                   Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────┐                   ┌──────────────────────────────────┐
│ Pi Coding Agent     │                   │ oMLX server (port 8000)         │
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
cp configs/omlx/pi-models.json ~/.pi/agent/models.json
```

Custom model config at `~/.pi/agent/models.json`:

```json
{
  "providers": {
    "macstudio": {
      "baseUrl": "http://<MAC_STUDIO_IP>:8000/v1",
      "api": "openai-completions",
      "apiKey": "<YOUR_API_KEY>",
      "compat": {
        "supportsUsageInStreaming": false,
        "supportsDeveloperRole": false,
        "maxTokensField": "max_tokens"
      },
      "models": [
        {
          "id": "mlx-community/Qwen3-Coder-Next-4bit",
          "name": "Qwen3 Coder (Mac Studio)",
          "reasoning": false,
          "input": ["text"],
          "contextWindow": 170000,
          "maxTokens": 8192,
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 }
        }
      ]
    }
  }
}
```

Key settings:
- `api: "openai-completions"` — oMLX speaks OpenAI Chat Completions format
- `apiKey` is required by Pi; oMLX uses it for authentication
- `supportsUsageInStreaming: false` — oMLX may not include usage data in streaming responses
- `maxTokensField: "max_tokens"` — oMLX uses the older field name (not `max_completion_tokens`)
- Cost is all zeros (local model, no billing)
- The `models.json` file hot-reloads — no restart needed when editing

## Testing

1. **Connectivity check**:
   ```bash
   curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
     -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool
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

- Verify the server is running: `curl -s http://<MAC_STUDIO_IP>:8000/v1/models -H "Authorization: Bearer <YOUR_API_KEY>"`
- Restart oMLX:
  ```bash
  brew services restart omlx
  ```

You can also verify server and model status via the admin panel at `http://<MAC_STUDIO_IP>:8000/admin`.

### Model not appearing in Pi

- Check `~/.pi/agent/models.json` is valid JSON: `python3 -m json.tool ~/.pi/agent/models.json`
- The file hot-reloads, but if it doesn't appear, restart Pi

### Tool calling issues

- Qwen3-Coder-Next-4bit may not handle all tool-calling formats perfectly
- This is a model quality issue, not a configuration problem
- If tool calls fail, try simpler prompts or test with a different model

### 422 Unprocessable Entity with reasoning models

Pi sends `role: "developer"` (OpenAI's newer role) for system prompts when `model.reasoning: true`. Local servers (oMLX, mlx-openai-server, vllm-mlx) only accept `system | user | assistant | tool`, causing a 422 validation error.

**Fix:** Add `"supportsDeveloperRole": false` to the provider's `compat` block in `~/.pi/agent/models.json`. This tells Pi to use `role: "system"` instead.

### Slow or hanging responses

- Check Mac Studio memory pressure: `ssh macstudio "memory_pressure"`
- Reduce `contextWindow` in models.json if the model runs out of memory

## Changing the Model

1. Load the new model on Mac Studio (see `../server/omlx/summary.md` "Changing the LLM Model")
2. Update `~/.pi/agent/models.json`:
   - Change `id` to the new model identifier
   - Update `name`, `contextWindow`, and `maxTokens` as appropriate
3. Pi hot-reloads `models.json` — no restart needed

## Comparison with Other Agent Setups

| | Claude Code | OpenCode | Pi |
|---|---|---|---|
| API format | Anthropic (native) | OpenAI (native) | OpenAI (native) |
| Proxy needed | No | No | No |
| Config file | `~/.claude/macstudio-settings.json` | `~/.config/opencode/opencode.json` | `~/.pi/agent/models.json` |
| Launch command | `claude-local` | `opencode` / `oc` | `pi` |
