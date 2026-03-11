# OpenCode Setup: WSL Linux → Mac Studio LLM Server

OpenCode on WSL connects **directly** to the mlx-lm server's OpenAI-compatible endpoint — no proxy needed.

## Architecture

```
WSL Linux (192.168.31.x via eth2)        Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌─────────────────────────┐              ┌──────────────────────────────────┐
│ OpenCode                │              │ mlx-lm server (port 8080)       │
│   openai-compatible     │──── LAN ────>│   Qwen3-Coder-Next-4bit         │
│   direct connection     │              │   /v1/chat/completions          │
└─────────────────────────┘              └──────────────────────────────────┘
```

## Prerequisites

- WSL2 with `eth2` on the `192.168.31.x` subnet (same LAN as Mac Studio)
- Mac Studio mlx-lm server running on port 8080
- OpenCode installed in WSL

## Step 1: Fix WSL Routing

WSL2 may have multiple network interfaces. If your `eth2` is on `192.168.31.x`, you need to ensure traffic to the Mac Studio is routed through it rather than the default interface.

Check your interfaces:
```bash
ifconfig
# Look for eth2: inet 192.168.31.x
```

Add the route:
```bash
sudo ip route add 192.168.31.0/24 dev eth2
```

Verify connectivity:
```bash
curl -s http://<MAC_STUDIO_IP>:8080/v1/models | python3 -m json.tool
```

### Make the Route Persistent

WSL2 loses `ip route` changes on restart. To persist, add to `/etc/wsl.conf` or use a startup script.

Option: Add to `~/.bashrc` or `~/.zshrc`:
```bash
# Ensure Mac Studio LAN route via eth2 on WSL startup
if ! ip route | grep -q "192.168.31.0/24"; then
  sudo ip route add 192.168.31.0/24 dev eth2 2>/dev/null
fi
```

Then allow passwordless sudo for this command by adding to `/etc/sudoers` (via `sudo visudo`):
```
%sudo ALL=(ALL) NOPASSWD: /sbin/ip route add 192.168.31.0/24 dev eth2
```

## Step 2: Install OpenCode

```bash
# Via npm
npm install -g opencode-ai

# Or check https://opencode.ai for latest install method
```

Verify: `opencode --version`

## Step 3: Configure OpenCode

```bash
mkdir -p ~/.config/opencode
```

Create `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "macstudio": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://<MAC_STUDIO_IP>:8080/v1",
        "apiKey": "not-needed",
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
  "small_model": "macstudio/mlx-community/Qwen3-Coder-Next-4bit",
  "agents": {
    "coder": {
      "model": "macstudio/mlx-community/Qwen3-Coder-Next-4bit"
    }
  }
}
```

Note: The `agents.coder` block is required by newer versions of OpenCode — without it you'll get `Error: agent coder not found`.

## Testing

1. **Connectivity check**:
   ```bash
   curl -s http://<MAC_STUDIO_IP>:8080/v1/models | python3 -m json.tool
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

## Troubleshooting

### `Error: agent coder not found`

Add the `agents` block to your config:
```json
"agents": {
  "coder": {
    "model": "macstudio/mlx-community/Qwen3-Coder-Next-4bit"
  }
}
```

### Curl to Mac Studio times out

Check routing — traffic may be going through the wrong interface:
```bash
ip route get <MAC_STUDIO_IP>
# Should show: dev eth2
```

If not, add the route:
```bash
sudo ip route add 192.168.31.0/24 dev eth2
```

### Can't connect to Mac Studio

- Verify server is running: `curl http://<MAC_STUDIO_IP>:8080/v1/models`
- Check mlx-lm from MacBook: `ssh macstudio "launchctl list | grep mlx"`
- Restart mlx-lm from MacBook:
  ```bash
  ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist"
  ```
