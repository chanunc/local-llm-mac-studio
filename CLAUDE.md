# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Documentation and configuration for a local LLM network centered on a **Mac Studio M3 Ultra (96GB)**. The primary server is **vllm-mlx** running `mlx-community/Ling-2.6-flash-mlx-6bit` (sparse 104B / 7.4B-active `bailing_hybrid`, 6-bit MLX, ~80 GB; deployed 2026-04-29 — requires three local patches, see Known Issues). **llmster** (LM Studio headless, port 1234) was added 2026-04-30 as the recommended server for standard MLX models — 3-5× faster end-to-end than vllm-mlx on agent loops. **oMLX** is available as a multi-model server with SSD caching when model variety is needed. vllm-mlx and oMLX speak OpenAI and Anthropic API natively on port 8000; llmster speaks OpenAI only on port 1234.

**Data flow:**
```
MacBook / Linux / WSL  ──── LAN ────>  Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
  Claude Code                            vllm-mlx (primary) :8000
  OpenCode                               mlx-openai-server :8000
  OpenClaw                               oMLX (multi-model) :8000
  Pi                                     vmlx (JANGTQ) :8000
                                         llmster (LM Studio) :1234
                                         OpenAI + Anthropic API native (llmster: OpenAI only)
```

SSH aliases: `macstudio` (Mac Studio over LAN), `macstudio-ts` (Mac Studio over Tailscale), `narutaki` (Linux client).

## Architecture

- **Primary server:** vllm-mlx pip-installed in `~/vllm-mlx-env/` on Mac Studio. **Production model**: `mlx-community/Ling-2.6-flash-mlx-6bit` (104B/7.4B-active `bailing_hybrid` MoE, 6-bit MLX, ~80 GB; deployed 2026-04-29 — requires PR #1227 vendoring + threadlocal-stream patch + inline-gen patch, see Known Issues for the full recipe). Started manually via `~/vllm-mlx-env/bin/vllm-mlx serve` with `--enable-auto-tool-choice --tool-call-parser hermes`. The `run_vllm_jang.py` wrapper is used for JANG-format models (e.g. Qwen3.6-27B JANG 4M dense+VL fallback).
- **Feature-rich alternative:** mlx-openai-server pip-installed in `~/mlx-openai-server-env/` on Mac Studio. Trie-based prompt caching, speculative decoding, Qwen3.5 reasoning parser, multi-model YAML config with process isolation. 4-15% overhead (worse than vllm-mlx at long contexts). OpenAI API only. JANG support via `.pth` patch (`jang_patch.pth` + `jang_mlx_patch.py` in venv site-packages), activated by `JANG_PATCH_ENABLED=1` env var. Survives pip upgrades. Current roster in `~/mlx-openai-server-multimodel.yaml`: `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` + `mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit`.
- **Multi-model server:** oMLX installed via Homebrew on Mac Studio, with AlexTzk fork overlay for JANG support (PR #364). Config lives in `~/.omlx/` on the Mac Studio (not in this repo). Models are MLX safetensors or JANG mixed-precision format stored in `~/.omlx/models/`.
- **JANGTQ server:** vmlx via the MLX Studio DMG (v1.3.65+) bundled Python at `/Applications/vMLX.app/Contents/Resources/bundled-python/python/`. Only route today for TurboQuant-weight models (`*JANGTQ*` / `*JANGTQ-CRACK*`) because the public `jang-tools` pypi package lacks `load_jangtq` + the `turboquant/*kernel*` Metal kernels ([jjang-ai/jangq#5](https://github.com/jjang-ai/jangq/issues/5)). Runs headlessly — no GUI session needed despite Electron packaging. Invoke as `python3 -m vmlx_engine.cli serve …` (the bundled `bin/vmlx` shebang points at the maintainer's build tree; the CLI module works fine). OpenAI + Anthropic + Ollama API compatible. Incompatible flags: `--smelt` and `--flash-moe` raise on `weight_format=mxtq` ([vmlx#81](https://github.com/jjang-ai/vmlx/issues/81)).
- **Client configs** (`configs/client/`): Organized by server type — `configs/client/vllm-mlx/` for primary server, `configs/client/mlx-openai-server/` for feature-rich multi-model, `configs/client/omlx/` for full multi-model roster, `configs/client/vmlx/` for JANGTQ CRACK models, `configs/client/llmster/` for LM Studio headless on port 1234 (added 2026-04-30, currently OpenCode-only — full client config set is deferred unless llmster graduates to permanent server status). IPs and API keys are stored as placeholders (`<MAC_STUDIO_IP>`, `<YOUR_API_KEY>`) — never commit real values.
- **Current state** (`docs/current.md`): Concise live-state pointer for production, sidecar, and fallback server/model choices. Update it whenever production state changes.
- **Scripts** (`scripts/`): Patch helpers, benchmark tools, and client-config utilities. See `scripts/README.md` before re-running patches after upgrades.
- **Plans** (`plans/`): Design documents for non-trivial changes before implementation. Plans are non-canonical; active plans live in `plans/active/`.

## Common Commands

```bash
# SSH to machines
ssh macstudio
ssh macstudio-ts
ssh narutaki

# Health check (vllm-mlx — no API key)
curl -s http://<MAC_STUDIO_IP>:8000/v1/models | python3 -m json.tool

# Health check (oMLX — needs API key)
curl -s http://<MAC_STUDIO_IP>:8000/v1/models \
  -H "Authorization: Bearer <YOUR_API_KEY>" | python3 -m json.tool

# Start vllm-mlx (current production primary: Ling-2.6-flash)
# Ling is plain MLX safetensors, not JANG, so use vllm-mlx directly.
# --tool-call-parser hermes is required because Ling emits <tool_call>{json}</tool_call>.
ssh macstudio "nohup ~/vllm-mlx-env/bin/vllm-mlx serve mlx-community/Ling-2.6-flash-mlx-6bit \
  --served-model-name mlx-community/Ling-2.6-flash-mlx-6bit \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  > /tmp/vllm-mlx.log 2>&1 &"

# Qwen3.6-27B JANG 4M remains the dense+VL fallback. Use run_vllm_jang.py with
# --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3.

# Switch to mlx-openai-server (multi-model, low overhead)
ssh macstudio "pkill -f vllm-mlx; /opt/homebrew/bin/brew services stop omlx; sleep 2; \
  JANG_PATCH_ENABLED=1 nohup ~/mlx-openai-server-env/bin/mlx-openai-server launch \
  --config ~/mlx-openai-server-multimodel.yaml --no-log-file \
  > /tmp/mlx-openai-server.log 2>&1 &"

# Switch to oMLX (multi-model, 9 models)
ssh macstudio "pkill -f mlx-openai-server; pkill -f vllm-mlx; pkill -f vmlx_engine; sleep 2; /opt/homebrew/bin/brew services start omlx"

# Switch to vmlx (JANGTQ CRACK models — bundled-Python headless path)
# --enable-auto-tool-choice + --tool-call-parser qwen3 are required for OpenCode / Claude Code tool use.
#   Without them the parser stays off and the model emits raw <tool_call>… XML inside `content`,
#   which clients render as plain text (model "hallucinates" tool names).
# --reasoning-parser qwen3 is required for Qwen3 thinking models (JANGTQ4-CRACK, Qwen3.5-VL CRACK).
#   Without it the model's <think>…</think> block is dumped into `content` and OpenCode renders
#   the raw thought process as the assistant's visible reply ("thinking nonsense").
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; /opt/homebrew/bin/brew services stop omlx; sleep 2; \
  BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python; \
  SNAP=~/.cache/huggingface/hub/models--dealignai--MiniMax-M2.7-JANGTQ-CRACK/snapshots/033d5537f48f2f836ce3dfbe392304a2b30f8536; \
  nohup \$BP/bin/python3 -m vmlx_engine.cli serve \$SNAP --host 0.0.0.0 --port 8000 \
    --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 > /tmp/vmlx.log 2>&1 &"

# Switch back to vllm-mlx
ssh macstudio "pkill -f mlx-openai-server; pkill -f vmlx_engine; /opt/homebrew/bin/brew services stop omlx; sleep 2"
# then start vllm-mlx as above

# View logs
ssh macstudio "tail -20 /tmp/vllm-mlx.log"            # vllm-mlx
ssh macstudio "tail -20 /tmp/mlx-openai-server.log"    # mlx-openai-server
ssh macstudio "tail -20 ~/.omlx/logs/server.log"       # oMLX
ssh macstudio "tail -20 /tmp/vmlx.log"                 # vmlx

# Upgrade all client tools (MacBook)
brew upgrade claude-code anomalyco/tap/opencode pi-coding-agent

# Upgrade oMLX (Mac Studio)
ssh macstudio "/opt/homebrew/bin/brew upgrade omlx"
```

Use `macstudio-ts` instead of `macstudio` when you are connected over Tailscale rather than the local LAN.

## Editing Workflow

### Sync Policy (Read this first when changing live state)

This repo is the operations notebook for a live Mac Studio LLM stack. Every model deployment, server change, production switch, or benchmark run touches **multiple** docs. Skipping any of them produces the kind of drift that bit us 2026-04-30 (README still claimed Qwen3.6-27B JANG 4M was primary three days after Ling took over; configs/README.md was 32 days behind).

**Hard rule:** When you take an action that changes live state, the same change must land in every doc that asserts the prior state. Use the per-event checklists below. Do not skip "minor" docs — drift compounds across sessions.

#### Event 1: Deploying a new server type (e.g. llmster, future Ollama)

If you stand up a new server type on the Mac Studio, all of these must be updated in the same PR/commit:
- `README.md` — data flow diagram, Quick Start launch + stop snippets, Health Check (curl + log tail), Servers table row (with link to `docs/server/<name>/summary.md`), maintenance line, Known Limitations entry
- `docs/current.md` — add the new server if it is live, sidecar, or a documented fallback
- `CLAUDE.md` **and `AGENTS.md`** (kept in sync, content identical except for the agent-name header) — overview paragraph, Architecture bullet, data flow diagram, Common Commands launch + stop, Editing Workflow scope note
- `configs/README.md` — bump `Last updated` date, Server Roles table row, new `client/<name>/` config-files section, Switching Servers command block
- `configs/client/<name>/opencode.json` — at minimum (other client configs are deferred until the server graduates to permanent status)
- `scripts/switch_opencode_config.py` — append `"<name>"` to the hardcoded `SERVERS` list
- `docs/server/<name>/summary.md` — full runbook matching the structure of `docs/server/vmlx/summary.md` (Overview, Architecture, Installation, Starting the server, Tool use and reasoning, Health check, Performance, Known limitations, See also)

If the new server does not support JANG/JANGTQ/`bailing_hybrid`, **also** update the "All servers support JANG…" line in `README.md` (currently reads "All servers except llmster support JANG…").

#### Event 2: Switching the production primary model on an existing server

When the live process on the Mac Studio changes (e.g. `pkill vllm-mlx; ... vllm-mlx serve <new-model>`), update:
- `README.md` — "Current `vllm-mlx` production primary" line under the Servers table, Quick Start launch-snippet comment, any inline references in Models table footnotes
- `docs/current.md` — production server/model/client-template row and fallback notes
- `CLAUDE.md` — overview paragraph (`Project` section), Architecture bullet ("Primary server" or equivalent), Common Commands example invocation
- `configs/README.md` — Server Roles table model column, the relevant `client/<server>/` section's Model description, the Switching Servers command block
- `configs/client/<server>/opencode.json` — `model` and `small_model` fields, plus the `models` map entry; do the equivalent in `claude-code-settings.json`, `pi-models.json`, `openclaw-provider.json`, `qwen-code-settings.json` if the server has them

After the switch, **capture the exact running command** (`ps -axo command= | grep ...`) and save it before the next stop — this is what restores production accurately.

#### Event 3: Adding a new model (any server)

When a new model file lands in `~/.cache/huggingface/`, `~/.omlx/models/`, or `~/.lmstudio/models/` and you serve it:
- `docs/models/model-summary.md` — add an Index entry **and** a per-model section with the standard spec table (Base Model, Quant, Format, Vendor, Parameters, Density, Quantization, Specialties, Tokens/sec, On-disk size, Context Size, License, Key Features), server config, performance numbers if benchmarked, caveats. Place the entry near siblings (Qwen3.6 family together, etc.)
- `README.md` Models table — one row with size, context, "Best For" cell, and a link to the new model-summary.md anchor
- The relevant `configs/client/<server>/*.json` files — add the new model to the `models` map (oMLX requires updating all 4 client config files; vllm-mlx is single-model so only update if it becomes the primary)
- If the model has a dedicated detail file (`model-summary-ling.md`, `model-summary-mimo-v2.5.md`), the model-summary.md entry should be a stub linking to it rather than duplicating content

If the model needs patches/wrappers (JANG, JANGTQ, `bailing_hybrid`, `mimo_v2`, etc.), document those in the same commit under `docs/server/<server>/jang-patch.md` or in the model's own summary file.

#### Event 4: Running a new benchmark

When you run `bench_api_server.py`, `bench_api_tool_call.py`, or `bench_agent_tool_call.py`:
- Save raw JSON output to `docs/models/benchmarks/<model-slug>/<benchmark-type>.json` (or `<benchmark-type>-<server>.json` for cross-server comparisons — see the `agent-bench-llmster.json` precedent)
- Update `docs/models/model-benchmark-<type>.md` — add the row to the cross-model summary table, add a per-model results section if one doesn't exist, link the raw JSON
- If the benchmark establishes a new fastest/slowest extreme, update the README Benchmarks section's headline tables
- If the benchmark reveals a production-impacting finding (faster server, broken model), update `model-summary.md` caveats and the relevant `model-summary-*.md` detail file

Do not commit bench JSONs that contain secrets or PII (these scripts don't generate any today, but verify before committing).

### Pre-commit drift check

Before committing any change to live state, grep for stale references across the four primary docs:
```bash
grep -n "<old-model-name>\|<old-primary>" README.md AGENTS.md CLAUDE.md configs/README.md docs/current.md docs/models/model-summary.md
```
Catch drift while the context is fresh, not three sessions later.

### Server-specific config rules

**oMLX models** (`configs/client/omlx/`) — when adding or removing, keep all of these in sync:
- `configs/client/omlx/opencode.json`
- `configs/client/omlx/pi-models.json`
- `configs/client/omlx/openclaw-provider.json`
- `configs/client/omlx/qwen-code-settings.json`
- `README.md` — Models & Benchmarks table
- `docs/models/model-summary.md` — per-model specs

`configs/client/omlx/claude-code-settings.json` only references one default model — update only if the default changes.

**mlx-openai-server configs** (`configs/client/mlx-openai-server/`) intentionally expose a stable superset of commonly used **compatible** model IDs. They do not have to mirror the exact live YAML on the Mac Studio; check `/v1/models` for the current live roster. Update them only when the compatible superset changes.

**vllm-mlx configs** (`configs/client/vllm-mlx/`) serve a single model and only need updating if the primary model changes (see Event 2 above).

**vmlx configs** (`configs/client/vmlx/`) target the JANGTQ CRACK model served out of the MLX Studio bundled Python. Update the model ID across all four files + the `README.md` Models table when the served JANGTQ model changes.

**llmster configs** (`configs/client/llmster/`) currently ship `opencode.json` only. If llmster graduates from provisional to permanent server status (sustained production use), backfill `claude-code-settings.json`, `pi-models.json`, `openclaw-provider.json`, `qwen-code-settings.json` to match the other servers.

**Model settings on Mac Studio** (`~/.omlx/model_settings.json`) are edited directly via SSH, then oMLX is restarted to apply. Changes there are separate from the client configs in this repo.

## oMLX Limitations

- **GGUF format**: Not supported — oMLX only loads MLX safetensors and JANG format.
- **MXFP8 quantization**: Not confirmed to work; use 4/6/8-bit MLX quantizations.
- **JANG + Nemotron-H**: JANG models with Nemotron-H architecture (latent MoE gate) fail with matmul shape mismatch — bug in PR #364's weight mapping. Non-Nemotron JANG models (e.g., Qwen3.5) work fine.
- **Qwen3.5-122B + OpenClaw**: HTTP 500 errors with large system prompts ([oMLX #42](https://github.com/jundot/omlx/issues/42)).
- **Dense 27B model + OpenClaw**: Too slow (all 27B params per token, no MoE sparsity).
- **Starlette 1.0 dashboard bug**: oMLX v0.2.20 pulls starlette 1.0.0 which breaks the admin dashboard. Fix: `pip install "starlette==0.46.2"` in the oMLX venv ([oMLX #361](https://github.com/jundot/omlx/issues/361)).

## Known Issues

- **SSH timeouts**: Fixed by `sudo pmset -a sleep 0 disksleep 0 displaysleep 10` on Mac Studio. If it returns, verify with `ssh macstudio "pmset -g | grep sleep"`.
- **Hot cache patch**: `scripts/patch_omlx_cache.py` must be re-applied after every `brew upgrade omlx` or fork reinstall. It patches `model_settings.py` and `engine_pool.py` inside the oMLX package to support per-model `hot_cache_max_size` in `~/.omlx/model_settings.json`. In v0.2.20, `parse_size` moved from `omlx.utils` to `omlx.config` — the patch script handles this.
- **JANG fork overlay**: oMLX currently runs with AlexTzk/omlx fork (PR #364) pip-installed over the Homebrew v0.2.20 base. The original omlx package is backed up at `/opt/homebrew/.../omlx.bak`. `brew upgrade omlx` will overwrite the fork — re-apply fork + patches after upgrades.
- **vmlx bundled-Python shebang**: the bundled `bin/vmlx` script has a hardcoded shebang pointing at the maintainer's build path (`/Users/eric/mlx/vllm-mlx/panel/bundled-python/python/bin/python3`). Always invoke via `$BP/bin/python3 -m vmlx_engine.cli serve …` (matches the CHANGELOG "Bundled spawn uses `python3 -m vmlx_engine.cli serve` (avoids shebang issues)" note). `BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python`. Re-applies on each DMG upgrade — the app bundle is self-contained, no homebrew coupling.
- **vmlx MLLM tools-dropped bug**: vmlx 1.0.3 (MLX Studio v1.3.65 bundled Python) drops the OpenAI `tools[]` array on the MLLM code path — `SimpleEngine.chat()` / `.stream_chat()` extract `tools` as a positional param then forward `mllm_kwargs = dict(kwargs)` which no longer contains it, and `MLLM._apply_chat_template` ignores `tools` entirely. Symptom: `prompt_tokens` stays tiny (~24) regardless of how many tools the client sends; model emits `curl` / `fetch` as prose. Fix: `scripts/patch_vmlx_jangtq_mllm_tools.py` — patches `vmlx_engine/engine/simple.py` (both MLLM branches forward `template_tools`) and `vmlx_engine/models/mllm.py` (`_apply_chat_template` accepts `tools`, both call sites pop + pass it). Idempotent. Run once on macstudio (`ssh macstudio "$BP/bin/python3 ~/setup-llm-macstu/scripts/patch_vmlx_jangtq_mllm_tools.py"`) after every MLX Studio DMG upgrade. Required for OpenCode / Claude Code tool use against any `is_mllm=True` model (Qwen3.6-VL JANGTQ4-CRACK, Qwen3.5-VL-122B CRACK).
- **Ling-2.6-flash deployment**: `mlx-community/Ling-2.6-flash-mlx-6bit` (`bailing_hybrid`) requires three patches against mlx-lm 0.31.3 + vllm-mlx 0.2.6 to load:
  1. Vendor `mlx_lm/models/bailing_hybrid.py` from open PR [ml-explore/mlx-lm#1227](https://github.com/ml-explore/mlx-lm/pull/1227) (otherwise `ValueError: Model type bailing_hybrid not supported`).
  2. `scripts/patch_mlx_lm_threadlocal_stream.py` — converts module-level `generation_stream` into a per-thread lazy accessor (otherwise `RuntimeError: There is no Stream(gpu, 1) in current thread` from worker threads).
  3. `scripts/patch_vllm_mlx_inline_gen.py` — replaces `await asyncio.to_thread(...)` calls in `vllm_mlx/engine/simple.py` with direct sync calls (otherwise the model's `mx.fast.metal_kernel` SSM/GLA kernels can't be invoked from worker threads even after #2). Run inline on the asyncio loop.
  Server flags: `--enable-auto-tool-choice --tool-call-parser hermes` (Ling emits Hermes-format `<tool_call>{json}</tool_call>` blocks; `qwen3` is not a valid choice in vllm-mlx 0.2.6 and `qwen3_coder` expects XML body). Caps at 64K context on M3 Ultra (96 GB) — 128K OOMs. mlx-openai-server is incompatible: its prompt-cache prefill in the inference-worker thread is more deeply thread-coupled than vllm-mlx and patch #3 doesn't apply directly. Re-apply patches 2 & 3 after `pip install -U vllm-mlx` or `pip install -U mlx-lm`.
