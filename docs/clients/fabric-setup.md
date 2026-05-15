# Fabric Setup: Client → Mac Studio LLM Server

[Fabric](https://github.com/danielmiessler/Fabric) is a **prompt-pattern CLI**: it wraps your input in one of 250+ curated, version-controlled prompts ("patterns") before sending it to any OpenAI-compatible endpoint. In this lab it connects via its **LM Studio vendor** (a generic OpenAI `/v1` client) to any Mac Studio server — validated against the mlx-lm ChindaMT-4B Thai↔EN sidecar on port 8080.

## Index
- [Architecture](#architecture)
- [Unique capability](#unique-capability)
- [Installation](#installation)
- [Configuration](#configuration)
- [Execution](#execution)
- [Troubleshooting](#troubleshooting)
- [See also](#see-also)

## 🏗️ Architecture

```
MacBook                              Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────────┐               ┌─────────────────────────────────────┐
│ fabric              │               │ mlx-lm sidecar (port 8080)          │
│  LM Studio vendor   │── LAN ───────>│   ChindaMT-4B  /v1/chat/completions │
│  ~/.config/fabric   │               │   (or any OpenAI /v1 server)        │
└────────────────────┘               └─────────────────────────────────────┘
```

Fabric has no native mlx-lm plugin. Its **LM Studio vendor** is a generic OpenAI-compatible HTTP client (`{base}/models`, `{base}/chat/completions`) and is the correct vendor for every `/v1`-speaking server in this lab. Do **not** use Fabric's native OpenAI vendor — that one targets the Responses API (`/v1/responses`), which the mlx servers don't serve.

## 💡 Unique capability

The other CLI prompt clients ([`llm` / `aichat` / `mods`](cli-prompt-clients.md)) send your text mostly as-is. Fabric's differentiator is its **pattern library** — 250+ curated, opinionated system prompts (`summarize`, `extract_wisdom`, `analyze_claims`, `create_art_prompt`, …) maintained upstream and synced into `~/.config/fabric/patterns/`.

- `fabric -p <pattern>` wraps stdin in that pattern's system prompt — reproducible, no re-engineering each time.
- `fabric -l` lists patterns; `fabric --readpattern=<name>` prints one; `fabric -U` updates them.
- Built-in input adapters the others lack: `-y <youtube-url>` (transcript), `-u <url>` (Jina scrape), `--session` (multi-turn memory).

Trade-off: patterns are general-LLM prompts. Against a **narrow model like ChindaMT (translation-only)** they produce garbage — use bare `fabric` (raw passthrough, no pattern) for ChindaMT, and reserve `-p` for a general model.

## ⚙️ Installation

```bash
brew install fabric-ai
```

The Homebrew binary is named `fabric-ai` and uses its own basename as the default pattern, so `fabric-ai` with no `-p` fails: `could not get pattern fabric-ai`. The upstream binary expects to be called `fabric` — fix once with a symlink on PATH:

```bash
ln -s /opt/homebrew/bin/fabric-ai ~/.local/bin/fabric   # ~/.local/bin survives brew upgrade
```

Verify: `fabric --version`

## 🧩 Configuration

Config is a single **global** file at `~/.config/fabric/.env` (not per-server). Run `fabric -S` for the interactive wizard, or write it directly:

```ini
DEFAULT_VENDOR=LM Studio
DEFAULT_MODEL=/Users/chanunc/mlx-models/chindamt-4b-4bit
LM_STUDIO_API_URL=http://<MAC_STUDIO_IP>:8080/v1
LM_STUDIO_API_KEY=not-needed
```

- **`LM_STUDIO_API_URL` must end in `/v1`.** Fabric's LM Studio plugin appends `/chat/completions` directly with no `/v1` of its own; mlx-lm 404s on `/chat/completions` and 200s on `/v1/chat/completions`.
- **`DEFAULT_MODEL` must be the exact ID the server reports** in `/v1/models`. `mlx_lm.server` echoes the literal `--model` string, so for ChindaMT this is the full path `/Users/chanunc/mlx-models/chindamt-4b-4bit` — a short alias triggers a HuggingFace 404.
- `LM_STUDIO_API_KEY` is required by the plugin but unused by mlx-lm — any placeholder works.
- Retarget another server by changing `LM_STUDIO_API_URL` (e.g. `:8000/v1` for vllm-mlx / oMLX) and `DEFAULT_MODEL` to that server's reported ID.

## ▶️ Execution

```bash
# 1. Raw passthrough (no pattern) — correct mode for ChindaMT translation
echo "Translate to Thai: Good evening" | fabric
fabric < document.txt
pbpaste | fabric

# 2. Pattern mode — needs a GENERAL model, not ChindaMT
echo "long text" | fabric -p summarize -m "<general-model-id>"
fabric -y "https://youtube.com/watch?v=..." -p extract_wisdom -m "<general-model-id>"
```

Per-run overrides: `-V "LM Studio"` (vendor), `-m <id>` (model), `-s` (stream), `-t 0.2` (temperature), `-r` (raw — skip temp/top_p, good for deterministic translation), `-o out.md` (write to file), `-c` (copy to clipboard).

Validated 2026-05-15 against ChindaMT-4B on :8080 — bare `fabric` round-trips both directions:
- EN→TH: "The Mac Studio is running a local translation model." → `Mac Studio กำลังใช้โมเดลแปลภาษาแบบท้องถิ่น`
- TH→EN: "ระบบแปลภาษาทำงานได้ดีมาก" → "The translation system works very well."

## ⚠️ Troubleshooting

| Symptom | Cause | Fix |
|:--|:--|:--|
| `could not get pattern fabric-ai` | Homebrew binary uses its own name as default pattern | Invoke via the `fabric` symlink (Installation), or pass an explicit `-p` |
| HTTP 404 on every call | `LM_STUDIO_API_URL` missing `/v1` | Append `/v1` to the URL in `.env` |
| HuggingFace 404 for the model | `DEFAULT_MODEL` is a short alias | Use the exact ID from `curl http://<MAC_STUDIO_IP>:8080/v1/models` |
| Patterns produce nonsense | Pattern run against ChindaMT (translation-only) | Use bare `fabric` for ChindaMT; reserve `-p` for a general model |
| Connection refused | mlx-lm sidecar not running | `ssh macstudio "tail /tmp/chindamt.log"`; restart per the launch snippet in the root README |

## See also

- [`cli-prompt-clients.md`](cli-prompt-clients.md) — `llm` / `aichat` / `mods` for pattern-free one-shots.
- [`../models/model-summary.md#chindamt-4b-thai--english-translation`](../models/model-summary.md#chindamt-4b-thai--english-translation) — ChindaMT-4B runbook + launch.
- [Fabric upstream](https://github.com/danielmiessler/Fabric) — pattern catalogue and updates.
