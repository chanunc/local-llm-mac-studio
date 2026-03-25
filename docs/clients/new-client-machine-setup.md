# Connect a New Machine to the Mac Studio LLM Server

This guide sets up Claude Code on a new machine to use the local LLM running on the Mac Studio M3 Ultra at `<MAC_STUDIO_IP>`.

## Index
- [Prerequisites](#prerequisites)
- [Step 1: Verify Network Connectivity](#step-1-verify-network-connectivity)
- [Step 2: Install Claude Code](#step-2-install-claude-code)
- [Step 3: Create Settings File](#step-3-create-settings-file)
- [Step 4: Add Shell Alias](#step-4-add-shell-alias)
- [Step 5: Test](#step-5-test)
  - [Basic test](#basic-test)
  - [Tool use test (verifies file reading works)](#tool-use-test-verifies-file-reading-works)
  - [Interactive session](#interactive-session)
- [Optional: SSH Access to Mac Studio](#optional-ssh-access-to-mac-studio)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- The Mac Studio oMLX server is already running on port 8000
- The new machine is on the same LAN as the Mac Studio
- Homebrew installed on the new machine (or Node.js 18+ if not on macOS)

## Step 1: Verify Network Connectivity

```bash
# Check the Mac Studio is reachable
ping -c 2 <MAC_STUDIO_IP>

# Check oMLX is responding (Anthropic format)
curl -s http://<MAC_STUDIO_IP>:8000/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: <YOUR_API_KEY>" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"mlx-community/Qwen3-Coder-Next-4bit","max_tokens":20,"messages":[{"role":"user","content":"Hi"}]}' \
  | python3 -m json.tool
```

You should see an Anthropic-format JSON response with `"type": "message"`. If not, the Mac Studio oMLX server may need to be started — see `../server/omlx-summary.md`.

## Step 2: Install Claude Code

```bash
brew install claude-code
```

Verify:
```bash
claude --version
```

## Step 3: Create Settings File

Copy the config from this repo:

```bash
mkdir -p ~/.claude
cp configs/omlx/claude-code-settings.json ~/.claude/macstudio-settings.json
```

Or create it manually:

```bash
cat > ~/.claude/macstudio-settings.json << 'EOF'
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://<MAC_STUDIO_IP>:8000",
    "ANTHROPIC_AUTH_TOKEN": "<YOUR_API_KEY>",
    "ANTHROPIC_MODEL": "mlx-community/Qwen3-Coder-Next-4bit"
  }
}
EOF
```

**Note:** If the Mac Studio's IP address is different on your network, replace `<MAC_STUDIO_IP>` with the correct IP.

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

If you want to manage the Mac Studio server from this machine:

```bash
# Generate SSH key (skip if you already have one)
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519

# Copy key to Mac Studio (will prompt for password)
ssh-copy-id <YOUR_USERNAME>@<MAC_STUDIO_IP>

# Add SSH alias
cat >> ~/.ssh/config << 'EOF'

Host macstudio
    HostName <MAC_STUDIO_IP>
    User <YOUR_USERNAME>
    IdentityFile ~/.ssh/id_ed25519
    ServerAliveInterval 60
    ServerAliveCountMax 3
EOF

chmod 600 ~/.ssh/config

# Verify
ssh macstudio "echo OK"
```

## Troubleshooting

**"Connection refused" on port 8000:**
The oMLX server isn't running. SSH into the Mac Studio and start it:
```bash
ssh macstudio "brew services start omlx"
```

**Slow or no response:**
The model may still be loading into GPU memory after a restart. Check logs:
```bash
ssh macstudio "tail -10 ~/.omlx/logs/server.log"
```

**"Host unreachable" or ping fails:**
The new machine is not on the same LAN, or the Mac Studio's IP has changed. Check the Mac Studio's current IP in System Settings > Network.
