# Connect a New Machine to the Mac Studio LLM Server

This guide sets up Claude Code on a new machine to use the local LLM running on the Mac Studio M3 Ultra at `192.168.1.181`.

## Prerequisites

- The Mac Studio LLM server is already running (mlx-lm on port 8080, claude-code-proxy on port 4000)
- The new machine is on the same LAN as the Mac Studio
- Node.js 18+ installed on the new machine

## Step 1: Verify Network Connectivity

```bash
# Check the Mac Studio is reachable
ping -c 2 192.168.1.181

# Check the proxy is responding
curl -s http://192.168.1.181:4000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: not-needed" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-sonnet-4-20250514","max_tokens":20,"messages":[{"role":"user","content":"Hi"}]}' \
  | python3 -m json.tool
```

You should see an Anthropic-format JSON response with `"type": "message"`. If not, the Mac Studio servers may need to be started — see `summary.md`.

## Step 2: Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

Verify:
```bash
claude --version
```

## Step 3: Create Settings File

Create the directory and settings file:

```bash
mkdir -p ~/.claude

cat > ~/.claude/macstudio-settings.json << 'EOF'
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://192.168.1.181:4000",
    "ANTHROPIC_AUTH_TOKEN": "not-needed"
  }
}
EOF
```

**Note:** If the Mac Studio's IP address is different on your network, replace `192.168.1.181` with the correct IP.

## Step 4: Add Shell Alias

Add to your shell config (`~/.zshrc` for macOS, `~/.bashrc` for Linux):

```bash
echo '' >> ~/.zshrc
echo '# Local LLM via Mac Studio' >> ~/.zshrc
echo "alias claude-local='claude --settings ~/.claude/macstudio-settings.json'" >> ~/.zshrc
source ~/.zshrc
```

## Step 5: Test

### Basic test
```bash
claude-local -p "Write a Python hello world"
```

### Tool use test (verifies file reading works)
```bash
echo "Hello from test file" > /tmp/test-local-llm.txt
claude-local -p "Read the file /tmp/test-local-llm.txt and tell me what it says"
```

### Interactive session
```bash
claude-local
```

## Optional: SSH Access to Mac Studio

If you want to manage the Mac Studio servers from this machine:

```bash
# Generate SSH key (skip if you already have one)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519

# Copy key to Mac Studio (will prompt for password)
ssh-copy-id chanunc@192.168.1.181

# Add SSH alias
cat >> ~/.ssh/config << 'EOF'

Host macstudio
    HostName 192.168.1.181
    User chanunc
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
EOF

chmod 600 ~/.ssh/config

# Verify
ssh macstudio "echo OK"
```

## Troubleshooting

**"Connection refused" on port 4000:**
The proxy isn't running. SSH into the Mac Studio and start it:
```bash
ssh macstudio "launchctl load ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist"
```

**"Connection refused" on port 8080:**
The mlx-lm server isn't running:
```bash
ssh macstudio "launchctl load ~/Library/LaunchAgents/com.chanunc.mlx-lm-server.plist"
```

**Slow or no response:**
The model may still be loading into GPU memory after a restart. Check logs:
```bash
ssh macstudio "tail -10 ~/llm-server/logs/mlx-lm-server.err"
```
Wait until you see `Uvicorn running` in the output.

**Tool calls appear as text instead of working:**
The proxy patch may have been lost. Reapply it:
```bash
ssh macstudio "SITE=~/llm-server/venv/lib/python3.12/site-packages/server && sed -i '' 's/is_claude_model = clean_model.startswith(\"claude-\")/is_claude_model = True/' \$SITE/fastapi.py"
ssh macstudio "launchctl unload ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist && launchctl load ~/Library/LaunchAgents/com.chanunc.litellm-proxy.plist"
```

**"Host unreachable" or ping fails:**
The new machine is not on the same LAN, or the Mac Studio's IP has changed. Check the Mac Studio's current IP in System Settings > Network.
