# Local LLM Agent Network (Mac Studio + Clients)

Welcome to the central repository for setting up and managing a local, high-performance LLM server and connecting various coding agents to it over a local network (LAN).

This setup uses a **Mac Studio M3 Ultra (96GB)** as the central "brain" to run massive LLMs locally, allowing multiple machines (MacBooks, Linux PCs) to use AI coding assistants without paying for API tokens or sending data to the cloud.

## 🌟 Quick Overview

- **The Brain:** A Mac Studio running the [oMLX](https://github.com/jundot/omlx) inference server. It natively speaks both OpenAI and Anthropic API formats.
- **The Models:** Running state-of-the-art quantized models like `Qwen3-Coder-Next` (6-bit for coding) and `Qwen3.5-122B` (for agentic tasks).
- **The Clients:** Tools like Claude Code, OpenCode, OpenClaw, and Pi running on other laptops/PCs, all pointing to the Mac Studio's IP address.

## 🧭 Where to Start

If you are completely new, follow these guides in order:

### 1. Server Setup (The Brain)
If you need to set up the Mac Studio from scratch, manage models, or troubleshoot the server:
👉 **[Read the Server Setup Guide](docs/server/omlx-summary.md)**

### 2. Client Setup (The Agents)
If the server is already running and you just want to connect a new laptop or use a specific tool, choose your guide:

- **[New Machine Setup](docs/clients/new-client-machine-setup.md)**: General guide for connecting a new laptop to the server.
- **[Claude Code](docs/clients/new-client-machine-setup.md)**: Setup for Anthropic's official CLI.
- **[OpenCode](docs/clients/opencode-setup.md)**: Setup for the OpenCode agent (MacBook/WSL).
- **[OpenClaw](docs/clients/openclaw-setup.md)**: Setup for the OpenClaw agent (Linux).
- **[Pi Coding Agent](docs/clients/pi-setup.md)**: Setup for Pi.

## 🛠️ Quick Commands

**Check if the server is alive (from any client):**
```bash
curl -s http://<MAC_STUDIO_IP>:8000/v1/models -H "Authorization: Bearer <YOUR_API_KEY>"
```

**Access the Admin Dashboard:**
Open `http://<MAC_STUDIO_IP>:8000/admin` in your web browser.

---
*For advanced troubleshooting and model discovery fixes, see the [Maintenance Guide](docs/server/omlx-maintenance.md).*
