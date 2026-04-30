# Client Docs

Setup and troubleshooting for machines that connect to the Mac Studio servers. Client config templates live under [`configs/clients/`](../../configs/clients/).

| Client | Doc | Config Template |
|:--|:--|:--|
| New machine setup | [`new-client-machine-setup.md`](new-client-machine-setup.md) | Depends on selected server |
| OpenCode | [`opencode-setup.md`](opencode-setup.md) | `configs/clients/<server>/opencode.json` |
| OpenCode analysis | [`opencode-analysis.md`](opencode-analysis.md) | Reference only |
| OpenClaw | [`openclaw-setup.md`](openclaw-setup.md) | `configs/clients/<server>/openclaw-provider.json` |
| OpenClaw issues | [`openclaw-known-issues.md`](openclaw-known-issues.md) | Reference only |
| Pi | [`pi-setup.md`](pi-setup.md) | `configs/clients/<server>/pi-models.json` |
| Qwen Code | [`qwen-code-setup.md`](qwen-code-setup.md) | `configs/clients/<server>/qwen-code-settings.json` |

`llmster` currently ships an OpenCode template only because it's provisional and OpenAI-only. If it graduates to permanent server status, backfill the other client templates per the [Sync Policy](../../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state).
