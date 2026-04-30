# Client Docs

Client setup and troubleshooting for machines that connect to the Mac Studio servers. Client config templates live under `configs/client/`.

| Client | Doc | Config Template |
|:--|:--|:--|
| New machine setup | [`new-client-machine-setup.md`](new-client-machine-setup.md) | Depends on selected server |
| OpenCode | [`opencode-setup.md`](opencode-setup.md) | `configs/client/<server>/opencode.json` |
| OpenCode analysis | [`opencode-analysis.md`](opencode-analysis.md) | Reference only |
| OpenClaw | [`openclaw-setup.md`](openclaw-setup.md) | `configs/client/<server>/openclaw-provider.json` |
| OpenClaw issues | [`openclaw-known-issues.md`](openclaw-known-issues.md) | Reference only |
| Pi | [`pi-setup.md`](pi-setup.md) | `configs/client/<server>/pi-models.json` |
| Qwen Code | [`qwen-code-setup.md`](qwen-code-setup.md) | `configs/client/<server>/qwen-code-settings.json` |

`llmster` currently has only an OpenCode template because it is provisional and OpenAI-only.
