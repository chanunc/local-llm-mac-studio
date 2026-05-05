# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

This repo is the operations notebook for a personal LLM **experimentation lab** on a **Mac Studio M3 Ultra (96GB)**. The work is **running and benchmarking new LLM models, and trying new inference techniques** (DFlash speculative decoding, JANG / TurboQuant quantisation, `bailing_hybrid` MoE, etc.) against whichever server best supports them. **There is no "production" model** — whatever model is currently loaded on a given server is the latest experiment, and is expected to be swapped out for the next one. Docs capture *what was tried, how it was deployed, and how it benchmarked* so future experiments don't re-discover the same patches and gotchas.

The available servers on the Mac Studio are:

- **vllm-mlx** (port 8000, OpenAI + Anthropic API) — most capable server for sparse-MoE / `bailing_hybrid` work. Most recently exercised with `mlx-community/Ling-2.6-flash-mlx-6bit` (104B/7.4B-active, ~80 GB), which needed three local patches — see Known Issues.
- **llmster** (LM Studio headless, port 1234, OpenAI only) — **current production main** (2026-05-05): `unsloth/granite-4.1-30b-GGUF` `Q8_0` (IBM Granite 4.1 30B instruct, Apache 2.0, 28.57 GiB). Censored/aligned; non-thinking instruct; **24.8 tok/s gen, browse 6.24 s / search 10.51 s**. LM Studio guardrail override required for initial load. Prior main (TrevorJS Gemma 4 26B A4B Uncensored Q8_0, 8/10 mlabonne, browse 2.93 s 🥇, 2026-05-03) remains on disk and reloadable. **Also on disk:** `DavidAU/gemma-4-31B-it-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Instruct-GGUF` Q6_k (Gemma 4 31B Heretic, 23.47 GiB, 7/10 mlabonne, 24.2 tok/s gen) — benchmarked sidecar, not active main.
- **dflash-mlx** (port 8098, OpenAI only) — DFlash speculative-decoding sidecar for single-shot decode-bound experiments. Standalone benchmarks on M3 Ultra (2026-05-01) show DFlash *regressing* vs baseline `mlx_lm` at 1k–4k token horizons; upstream's 1.33× speedup claim is M5-Max-specific. Kept as an upstream-feature-tracking sidecar, not a throughput win.
- **mlx-openai-server** (port 8000, OpenAI only) — feature-rich alternative with trie-based prompt caching, speculative decoding, and multi-model YAML config.
- **oMLX** (port 8000, OpenAI + Anthropic API) — multi-model server with SSD caching when model variety matters.
- **vmlx** (port 8000) — bundled-Python path for JANGTQ / TurboQuant CRACK models the public `jang-tools` package can't yet serve.

Only one of vllm-mlx, mlx-openai-server, oMLX, or vmlx can hold port 8000 at a time — switch by killing the current process before starting another (and see Event 4 pre-benchmark hygiene before any benchmark run). dflash-mlx (8098) and llmster (1234) can coexist with the port-8000 server.

**Skill: `/deploy-run-benchmark-uncen-model`** — for *uncensored* model deploys (HauhauCS, dealignai-CRACK, Hermes 4, Dolphin, abliterated, magnum, …) the six-phase recipe (hygiene → deploy → smoke + refusal + perf + agent → submodule + parent doc edits) is automated at `~/.claude/skills/deploy-run-benchmark-uncen-model/`. Runs Events 3 + 4 + 6 of the Sync Policy itself. Censored models still follow the manual flow under `configs/clients/<server>/`.

**Data flow:**
```
MacBook / Linux / WSL  ──── LAN ────>  Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
  Claude Code                            vllm-mlx :8000          ┐
  OpenCode                               mlx-openai-server :8000  │  one at a time
  OpenClaw                               oMLX (multi-model) :8000 │  on port 8000
  Pi                                     vmlx (JANGTQ) :8000     ┘
                                         llmster (LM Studio) :1234
                                         dflash-mlx (sidecar) :8098
                                         OpenAI + Anthropic API native (llmster + dflash-mlx: OpenAI only)
```

SSH aliases: `macstudio` (Mac Studio over LAN), `macstudio-ts` (Mac Studio over Tailscale), `narutaki` (Linux client).

## Architecture

- **vllm-mlx:** pip-installed in `~/vllm-mlx-env/` on Mac Studio. Most capable server for sparse-MoE / `bailing_hybrid` work. **Last exercised model**: `mlx-community/Ling-2.6-flash-mlx-6bit` (104B/7.4B-active `bailing_hybrid` MoE, 6-bit MLX, ~80 GB; deployed 2026-04-29 — requires PR #1227 vendoring + threadlocal-stream patch + inline-gen patch, see Known Issues for the full recipe). Started manually via `~/vllm-mlx-env/bin/vllm-mlx serve` with `--enable-auto-tool-choice --tool-call-parser hermes`. The `run_vllm_jang.py` wrapper is used for JANG-format models (e.g. Qwen3.6-27B JANG 4M dense+VL fallback).
- **Feature-rich alternative:** mlx-openai-server pip-installed in `~/mlx-openai-server-env/` on Mac Studio. Trie-based prompt caching, speculative decoding, Qwen3.5 reasoning parser, multi-model YAML config with process isolation. 4-15% overhead (worse than vllm-mlx at long contexts). OpenAI API only. JANG support via `.pth` patch (`jang_patch.pth` + `jang_mlx_patch.py` in venv site-packages), activated by `JANG_PATCH_ENABLED=1` env var. Survives pip upgrades. Current roster in `~/mlx-openai-server-multimodel.yaml`: `mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit` (JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K removed from disk 2026-05-05 — update YAML before restarting mlx-openai-server).
- **Multi-model server:** oMLX installed via Homebrew on Mac Studio, with AlexTzk fork overlay for JANG support (PR #364). Config lives in `~/.omlx/` on the Mac Studio (not in this repo). Models are MLX safetensors or JANG mixed-precision format stored in `~/.omlx/models/`.
- **DFlash sidecar:** dflash-mlx pip-installed in `~/dflash-mlx-env/` on Mac Studio (Python 3.11). **Pair**: `mlx-community/Qwen3.6-35B-A3B-4bit` target + `z-lab/Qwen3.6-35B-A3B-DFlash` drafter. Wraps `mlx_lm.server` (in 0.1.4.1+ from main-branch git only — PyPI 0.1.0 has no tool-calling). Speculative decoding via block-diffusion drafter, 86.7% draft acceptance on Qwen3.6, 74-89 tok/s sustained decode. OpenAI API on port **8098**. Requires three local patches: `patch_dflash_mlx_serve.py` (two upstream bugs in `DFlashModelProvider` + startup banner), `patch_mlx_lm_match.py` (tool-detection trie reset), and `patch_dflash_mlx_host.py` only if pinned to 0.1.0. `--draft-model` flag is **required** for Qwen3.6 (built-in `DRAFT_REGISTRY` only auto-resolves Qwen3.5 family pairs). Provisional posture (mirrors llmster) — `configs/clients/dflash-mlx/opencode.json` only.
- **JANGTQ server:** vmlx via the MLX Studio DMG (v1.3.65+) bundled Python at `/Applications/vMLX.app/Contents/Resources/bundled-python/python/`. **Currently stopped** (2026-05-02 — the deploy-and-benchmark of prithivMLmods Aggressive on llmster reclaimed the active server slot per Event 4). Last main: `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` (was deployed 2026-05-01 for fair agent benchmarking; restartable via the launch shape in [`docs/current.md`](docs/current.md)). Only route today for TurboQuant-weight models (`*JANGTQ*` / `*JANGTQ-CRACK*`) because the public `jang-tools` pypi package lacks `load_jangtq` + the `turboquant/*kernel*` Metal kernels ([jjang-ai/jangq#5](https://github.com/jjang-ai/jangq/issues/5)). Runs headlessly — no GUI session needed despite Electron packaging. Invoke as `python3 -m vmlx_engine.cli serve …` (the bundled `bin/vmlx` shebang points at the maintainer's build tree; the CLI module works fine). OpenAI + Anthropic + Ollama API compatible. Incompatible flags: `--smelt` and `--flash-moe` raise on `weight_format=mxtq` ([vmlx#81](https://github.com/jjang-ai/vmlx/issues/81)).
- **Client configs** (`configs/clients/`): Organized by server type — `configs/clients/vllm-mlx/` for primary server, `configs/clients/mlx-openai-server/` for feature-rich multi-model, `configs/clients/omlx/` for full multi-model roster, `configs/clients/vmlx/` for JANGTQ CRACK models, `configs/clients/llmster/` for LM Studio headless on port 1234 (added 2026-04-30, currently OpenCode-only — full client config set is deferred unless llmster graduates to permanent server status), `configs/clients/dflash-mlx/` for DFlash speculative-decoding sidecar on port 8098 (added 2026-04-30, currently OpenCode-only — same provisional posture as llmster). IPs and API keys are stored as placeholders (`<MAC_STUDIO_IP>`, `<YOUR_API_KEY>`) — never commit real values.
- **Current state** (`docs/current.md`): Concise live-state pointer for production, sidecar, and fallback server/model choices. Update it whenever production state changes.
- **Scripts** (`scripts/`): Split into `scripts/patches/` (re-applied after upstream package upgrades — `patch_omlx_cache.py` runs after every `brew upgrade omlx`) and `scripts/bench/` (benchmark drivers). See `scripts/README.md`.
- **Plans** (`plans/`): Design documents for non-trivial changes before implementation. Plans are non-canonical; active plans live in `plans/active/`, completed in `plans/done/`, abandoned in `plans/archive/`.

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

# Start vllm-mlx (primary server — JANG model needs wrapper)
# --enable-auto-tool-choice + --tool-call-parser qwen3_coder are required for Qwen3.5/3.6 tool use.
#   The model emits XML tool calls (<function=name><parameter=key>value</parameter></function>),
#   not JSON. The qwen3_coder parser (aliased to HermesToolParser) handles this format.
#   Using --tool-call-parser qwen will NOT work (it expects JSON inside <tool_call> tags).
# --reasoning-parser qwen3 extracts <think>…</think> into the reasoning field.
ssh macstudio "nohup ~/vllm-mlx-env/bin/python ~/run_vllm_jang.py serve \
  ~/.omlx/models/JANGQ-AI--Qwen3.6-27B-JANG_4M \
  --served-model-name JANGQ-AI/Qwen3.6-27B-JANG_4M \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  > /tmp/vllm-mlx.log 2>&1 &"

# To start the previous primary (Qwen3.5-122B-A10B-JANG_2S), swap both `~/.omlx/models/...` and `--served-model-name` to `JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S`. Same parser flags.

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
# --reasoning-parser qwen3 is required for Qwen3 thinking models (e.g. Qwen3.5-VL CRACK, JANGTQ4).
#   Without it the model's <think>…</think> block is dumped into `content` and OpenCode renders
#   the raw thought process as the assistant's visible reply ("thinking nonsense").
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; /opt/homebrew/bin/brew services stop omlx; sleep 2; \
  BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python; \
  SNAP=~/.cache/huggingface/hub/models--OsaurusAI--Qwen3.6-35B-A3B-JANGTQ4/snapshots/40c1de58e06a9737427e5d64938e56aa339a6204; \
  nohup \$BP/bin/python3 -m vmlx_engine.cli serve \$SNAP --host 0.0.0.0 --port 8000 \
    --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
    --continuous-batching > /tmp/vmlx.log 2>&1 &"

# Switch back to vllm-mlx
ssh macstudio "pkill -f mlx-openai-server; pkill -f vmlx_engine; /opt/homebrew/bin/brew services stop omlx; sleep 2"
# then start vllm-mlx as above

# Start dflash-mlx (provisional sidecar on port 8098 — does not displace port 8000)
# --draft-model REQUIRED for Qwen3.6 (DRAFT_REGISTRY auto-resolves Qwen3.5 only).
# Patches MUST be applied first (idempotent re-runs are no-ops):
#   ~/dflash-mlx-env/bin/python ~/setup-llm-macstu/scripts/patches/patch_dflash_mlx_serve.py
#   ~/dflash-mlx-env/bin/python ~/setup-llm-macstu/scripts/patches/patch_mlx_lm_match.py
ssh macstudio "nohup ~/dflash-mlx-env/bin/dflash-serve \
  --host 0.0.0.0 --port 8098 \
  --model mlx-community/Qwen3.6-35B-A3B-4bit \
  --draft-model z-lab/Qwen3.6-35B-A3B-DFlash \
  --temp 0.0 --max-tokens 512 \
  > /tmp/dflash-mlx.log 2>&1 &"

# Stop dflash-mlx
ssh macstudio "pkill -f dflash-serve"

# View logs
ssh macstudio "tail -20 /tmp/vllm-mlx.log"            # vllm-mlx
ssh macstudio "tail -20 /tmp/mlx-openai-server.log"    # mlx-openai-server
ssh macstudio "tail -20 ~/.omlx/logs/server.log"       # oMLX
ssh macstudio "tail -20 /tmp/vmlx.log"                 # vmlx
ssh macstudio "tail -20 /tmp/dflash-mlx.log"           # dflash-mlx

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

#### Canonical layers and where they live

The repo has three navigation layers. Every change to live state must keep all three in sync.

1. **Live-state pointer** — [`docs/current.md`](docs/current.md). One concise table for production server/model, sidecar, and fallbacks. Read it first; update it whenever production state changes.
2. **Sub-root README.md indexes** — every top-level content folder has a `README.md` acting as its canonical index. When you add, remove, rename, or move a file inside one of these folders, update its README in the same commit:

   | Folder | README | Indexes |
   |:--|:--|:--|
   | `docs/servers/` | [`docs/servers/README.md`](docs/servers/README.md) | Server runbooks + maintenance docs |
   | `docs/models/` | [`docs/models/README.md`](docs/models/README.md) | Catalog, `per-model/`, `techniques/`, `benchmarks/`, `how-to/` |
   | `docs/clients/` | [`docs/clients/README.md`](docs/clients/README.md) | Client setup docs ↔ template mapping |
   | `configs/` | [`configs/README.md`](configs/README.md) | Server Roles table + Switching Servers |
   | `configs/clients/` | [`configs/clients/README.md`](configs/clients/README.md) | Per-server template layout |
   | `scripts/` | [`scripts/README.md`](scripts/README.md) | `bench/`, `patches/`, `switch_opencode_config.py` |
   | `plans/` | [`plans/README.md`](plans/README.md) | `active/`, `done/`, `archive/` indexes |

3. **Top-level docs** — `README.md`, `CLAUDE.md`, `AGENTS.md`. CLAUDE.md and AGENTS.md must stay content-identical except for the agent-name header (lines 1–3).

#### Event 1: Deploying a new server type (e.g. llmster, future Ollama)

If you stand up a new server type on the Mac Studio, all of these must be updated in the same PR/commit:
- `README.md` — data flow diagram, Quick Start launch + stop snippets, Health Check (curl + log tail), Servers table row (with link to `docs/servers/<name>/summary.md`), maintenance line, Known Limitations entry, "What lives where" table only if a new top-level folder is introduced
- `docs/current.md` — add the new server if it is live, sidecar, or a documented fallback
- `CLAUDE.md` **and `AGENTS.md`** — overview paragraph, Architecture bullet, data flow diagram, Common Commands launch + stop, Editing Workflow scope note. Mirror edits between the two files.
- `configs/README.md` — bump `Last updated` date, Server Roles table row, new `clients/<name>/` config-files section, Switching Servers command block
- `configs/clients/<name>/opencode.json` — at minimum (other client configs are deferred until the server graduates to permanent status)
- `configs/clients/README.md` — add the new server row to the Layout table; note any deferred templates
- `scripts/switch_opencode_config.py` — append `"<name>"` to the hardcoded `SERVERS` list
- `docs/servers/<name>/summary.md` — full runbook matching the structure of `docs/servers/vmlx/summary.md` (Overview, Architecture, Installation, Starting the server, Tool use and reasoning, Health check, Performance, Known limitations, See also)
- `docs/servers/README.md` — add the new server row to the runbook index, and to Maintenance And Patches if maintenance/patch docs exist

If the new server does not support JANG/JANGTQ/`bailing_hybrid`, **also** update the "All servers support JANG…" line in `README.md` (currently reads "All servers except llmster support JANG…").

#### Event 2: Switching the production primary model on an existing server

When the live process on the Mac Studio changes (e.g. `pkill vllm-mlx; ... vllm-mlx serve <new-model>`), update:
- `README.md` — "Current `vllm-mlx` production primary" line under the Servers table, Quick Start launch-snippet comment, any inline references in Models table footnotes
- `docs/current.md` — Production table row (server / model / launch shape / runbook link) and Fallbacks table if the previous primary becomes a fallback
- `CLAUDE.md` **and `AGENTS.md`** — overview paragraph (`Project` section), Architecture bullet ("Primary server" or equivalent), Common Commands example invocation
- `configs/README.md` — Server Roles table model column, the relevant `clients/<server>/` section's Model description, the Switching Servers command block
- `configs/clients/<server>/opencode.json` — `model` and `small_model` fields, plus the `models` map entry; do the equivalent in `claude-code-settings.json`, `pi-models.json`, `openclaw-provider.json`, `qwen-code-settings.json` if the server has them
- `docs/servers/<server>/summary.md` — Production model section if one exists; otherwise leave it
- `docs/models/model-summary.md` — flip "current production" / "previous production" markers if any model rows carry them

After the switch, **capture the exact running command** (`ps -axo command= | grep ...`) and save it before the next stop — this is what restores production accurately.

#### Event 3: Adding a new model (any server)

When a new model file lands in `~/.cache/huggingface/`, `~/.omlx/models/`, or `~/.lmstudio/models/` and you serve it:
- `docs/models/model-summary.md` — add an Index entry **and** a per-model section with the standard spec table (Base Model, Quant, Format, Vendor, Parameters, Density, Quantization, Specialties, Tokens/sec, On-disk size, Context Size, License, Key Features), server config, performance numbers if benchmarked, caveats. Place the entry near siblings (Qwen3.6 family together, etc.)
- `docs/models/per-model/model-summary-<slug>.md` — only if the model needs more than ~150 lines of detail (deployment recipe, patch list, failure analysis). The catalog entry should then be a stub linking here.
- `docs/models/README.md` — add a row to the Per-model deep dives table if you created a `per-model/` file
- `README.md` Models table — one row with size, context, "Best For" cell, and a link to the new model-summary.md anchor
- The relevant `configs/clients/<server>/*.json` files — add the new model to the `models` map (oMLX requires updating all 4 client config files; vllm-mlx is single-model so only update if it becomes the primary)
- If the model becomes production primary or sidecar, also follow Event 2 — at minimum `docs/current.md` and the launch-shape comment in `README.md`
- **If the user asks to "deploy and benchmark" a new model**, follow the pre-benchmark hygiene rule in Event 4 first: stop any other Mac Studio LLM server process before starting the new model, so the deploy-then-benchmark sequence runs on a clean machine.

If the model needs patches/wrappers (JANG, JANGTQ, `bailing_hybrid`, `mimo_v2`, etc.), the **technique-level explanation** belongs in `docs/models/techniques/model-<technique|quantization|architecture>-<name>.md` (canonical reference), and the **server-specific integration steps** in `docs/servers/<server>/jang-patch.md` or `docs/servers/<server>/summary.md`. Per-model deploy specifics (model ID, launch invocation) go in the model's own summary file. See Event 7 for the techniques-folder rules.

#### Event 4: Running a new benchmark

**Pre-benchmark hygiene (always do this first):** before launching the model under test, stop every other Mac Studio LLM server process so the benchmark reflects the target model alone, not residual GPU buffers, wired-memory KV cache, or file cache from a prior server. The Mac Studio has ~96 GB unified memory and most production models occupy 30–80 GB; leaving a prior server alive either OOMs the new launch or quietly contaminates tok/s, TTFT, and wired-memory readings. This is mandatory whenever the user asks to "deploy and benchmark" a new model — do it before the deploy step, not after.

```bash
# Stop everything benchmark-relevant on the Mac Studio, then verify the GPU/RAM is quiescent.
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; \
  pkill -f dflash-serve; pkill -f 'lms server'; \
  /opt/homebrew/bin/brew services stop omlx; sleep 3; \
  ps -axo pid,rss,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms |omlx' | grep -v grep || echo 'clean'; \
  memory_pressure | head -5"
```

**Do not restore the previously running model after the benchmark.** The newly deployed-and-benchmarked model stays running as the new main process on the Mac Studio — follow Event 2 to flip `docs/current.md`, the `README.md` Quick Start launch snippet, the relevant `CLAUDE.md` / `AGENTS.md` overview lines, and the `configs/clients/<server>/*.json` model fields so the docs match the live process. Restarting the prior model would just re-contaminate memory and undo the clean run you just paid for. Only restore the prior model if the user explicitly asks.

When you run `scripts/bench/bench_api_server.py`, `scripts/bench/bench_api_tool_call.py`, or `scripts/bench/bench_agent_tool_call.py`:
- Save raw JSON output to `docs/models/benchmarks/<model-slug>/<benchmark-type>.json` (or `<benchmark-type>-<server>.json` for cross-server comparisons — see the `agent-bench-llmster.json` precedent)
- Update the matching `docs/models/benchmarks/model-benchmark-<type>.md` — add the row to the cross-model summary table, add a per-model results section if one doesn't exist, link the raw JSON
- If you introduce a new benchmark *type* (rare), add a row in `docs/models/README.md`'s Benchmarks table
- If the benchmark establishes a new fastest/slowest extreme, update the README Benchmarks section's headline tables
- If the benchmark reveals a production-impacting finding (faster server, broken model), update `docs/models/model-summary.md` caveats, the relevant `docs/models/per-model/model-summary-<slug>.md` detail file, and `docs/current.md` if it drives a production switch (then continue with Event 2)

Do not commit bench JSONs that contain secrets or PII (these scripts don't generate any today, but verify before committing).

#### Event 5: Adding, renaming, or removing a script

When you change anything under `scripts/`:
- Add new files into the matching subdir — `scripts/bench/` for benchmark drivers, `scripts/patches/` for monkey-patches against installed server packages. Top-level `scripts/` is reserved for client-side helpers like `switch_opencode_config.py`.
- `scripts/README.md` — update the Benchmarks, Patches, or Client Config table to add/rename/remove the script
- If the script is a patch, link it from the relevant `docs/servers/<server>/maintenance.md` or `jang-patch.md` so the runbook explains when to re-run it
- If the script is a benchmark driver, update Event 4's listed names and add an entry in `docs/models/README.md`'s Benchmarks table when a new type is introduced
- If you rename or move a script, grep for stale references: `grep -rn "scripts/<old-name>" --include="*.md" --include="*.json" --include="*.py"`

#### Event 6: Adding, completing, or abandoning a plan

Plans are non-canonical research docs. They live under `plans/active/` (planned or in progress), `plans/done/` (implemented and kept for context), or `plans/archive/` (superseded or abandoned).

- New plan: create at `plans/active/plan-<slug>.md` with the status block (`Status: active`, `Created: YYYY-MM-DD`, `Canonical: no`); add a row to `plans/README.md`'s Active index
- Completing a plan: `git mv plans/active/<file> plans/done/<file>`, move the row in `plans/README.md` from Active to Done, and link the implementation (commits, code locations) at the top of the plan body
- Abandoning a plan: `git mv plans/active/<file> plans/archive/<file>`, move the row in `plans/README.md` from Active to Archive, and add a one-line "Archived because…" note at the top of the plan body
- Plans never claim live state on their own — operational truth must land in `docs/current.md`, `docs/servers/`, or the catalogs. A plan saying "production primary is X" does not make it so; the production switch follows Event 2.

#### Event 7: Adding or updating a technique / quantisation / architecture reference

Cross-cutting reference docs for inference-side techniques, weight quantisation formats, KV-cache compression, and model architectures live under `docs/models/techniques/`. They are the **canonical *what-it-is* reference**; server runbooks and per-model files cross-link in for the explanation rather than duplicating it.

- Filename carries the category prefix: `model-technique-<name>.md` for generation-time techniques (DFlash, prompt caching), `model-quantization-<name>.md` for weight or activation formats (JANG, TurboQuant/JANGTQ), `model-architecture-<name>.md` for model architectures whose deployment requires cross-cutting treatment (`bailing_hybrid`).
- New technique doc: lead with **what it is** in one paragraph, then *how it integrates with this stack*, then performance / known limitations / cross-references. Add a row to `docs/models/techniques/README.md`'s Index table.
- When a technique gets a new server integration: update the technique file's "How servers integrate it" / "Server compatibility" table, then add the server-specific operational steps in `docs/servers/<server>/<name>-patch.md` or `docs/servers/<server>/summary.md`. Server doc opens with a callout pointing to the technique file for the conceptual content.
- When a regression / quality bug / performance characteristic is discovered for a technique, update the technique file (canonical) — do not bury the analysis in a per-model file or a server runbook. Cross-link from the relevant `docs/models/benchmarks/` write-up.
- If the technique becomes operationally adopted as production, sidecar, or fallback, update `docs/current.md` and the relevant server runbook with a one-line conclusion + link back to the technique file.
- Pre-commit drift check for technique-folder edits: grep for stale references to the technique file by name across `docs/`, `plans/`, `README.md`, `CLAUDE.md`, `AGENTS.md`.

### Pre-commit drift check

Before committing any change to live state, grep for stale references across the primary docs:
```bash
grep -n "<old-model-name>\|<old-primary>" README.md AGENTS.md CLAUDE.md configs/README.md docs/current.md docs/models/model-summary.md
```
Catch drift while the context is fresh, not three sessions later.

### Server-specific config rules

**oMLX models** (`configs/clients/omlx/`) — when adding or removing, keep all of these in sync:
- `configs/clients/omlx/opencode.json`
- `configs/clients/omlx/pi-models.json`
- `configs/clients/omlx/openclaw-provider.json`
- `configs/clients/omlx/qwen-code-settings.json`
- `README.md` — Models & Benchmarks table
- `docs/models/model-summary.md` — per-model specs

`configs/clients/omlx/claude-code-settings.json` only references one default model — update only if the default changes.

**mlx-openai-server configs** (`configs/clients/mlx-openai-server/`) intentionally expose a stable superset of commonly used **compatible** model IDs. They do not have to mirror the exact live YAML on the Mac Studio; check `/v1/models` for the current live roster. Update them only when the compatible superset changes.

**vllm-mlx configs** (`configs/clients/vllm-mlx/`) serve a single model and only need updating if the primary model changes (see Event 2 above).

**vmlx configs** (`configs/clients/vmlx/`) target the JANGTQ CRACK model served out of the MLX Studio bundled Python. Update the model ID across all four files + the `README.md` Models table when the served JANGTQ model changes.

**llmster configs** (`configs/clients/llmster/`) currently ship `opencode.json` only. If llmster graduates from provisional to permanent server status (sustained production use), backfill `claude-code-settings.json`, `pi-models.json`, `openclaw-provider.json`, `qwen-code-settings.json` to match the other servers.

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
- **Hot cache patch**: `scripts/patches/patch_omlx_cache.py` must be re-applied after every `brew upgrade omlx` or fork reinstall. It patches `model_settings.py` and `engine_pool.py` inside the oMLX package to support per-model `hot_cache_max_size` in `~/.omlx/model_settings.json`. In v0.2.20, `parse_size` moved from `omlx.utils` to `omlx.config` — the patch script handles this.
- **JANG fork overlay**: oMLX currently runs with AlexTzk/omlx fork (PR #364) pip-installed over the Homebrew v0.2.20 base. The original omlx package is backed up at `/opt/homebrew/.../omlx.bak`. `brew upgrade omlx` will overwrite the fork — re-apply fork + patches after upgrades.
- **vmlx bundled-Python shebang**: the bundled `bin/vmlx` script has a hardcoded shebang pointing at the maintainer's build path (`/Users/eric/mlx/vllm-mlx/panel/bundled-python/python/bin/python3`). Always invoke via `$BP/bin/python3 -m vmlx_engine.cli serve …` (matches the CHANGELOG "Bundled spawn uses `python3 -m vmlx_engine.cli serve` (avoids shebang issues)" note). `BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python`. Re-applies on each DMG upgrade — the app bundle is self-contained, no homebrew coupling.
- **vmlx MLLM tools-dropped bug**: vmlx 1.0.3 silently drops `tools[]` on the MLLM code path. Symptom: tiny `prompt_tokens`, model emits `curl`/`fetch` as prose. Fix: `scripts/patches/patch_vmlx_jangtq_mllm_tools.py` (idempotent; re-apply after every DMG upgrade). Required for any `is_mllm=True` model. Full bug-by-bug breakdown: [`docs/models/techniques/model-quantization-turboquant.md` § MLLM tool-use bugs](docs/models/techniques/model-quantization-turboquant.md#mllm-tool-use-bugs).
- **dflash-mlx 0.1.4.1 + mlx-lm 0.31.3**: three patches required for tool-calling end-to-end (`patch_dflash_mlx_serve.py`, `patch_mlx_lm_match.py`, plus `patch_dflash_mlx_host.py` only on 0.1.0). PyPI ships 0.1.0 without tool-calling — install from main: `pip install 'git+https://github.com/bstnxbt/dflash-mlx.git'`. `DRAFT_REGISTRY` auto-resolves Qwen3.5 only — Qwen3.6 targets must pass `--draft-model` explicitly. Re-apply patches after `pip install -U`. Full bug-by-bug breakdown + cross-fork landscape: [`docs/models/techniques/model-technique-dflash.md`](docs/models/techniques/model-technique-dflash.md).
- **Ling-2.6-flash deployment**: `mlx-community/Ling-2.6-flash-mlx-6bit` (`bailing_hybrid`) requires three patches: vendor `bailing_hybrid.py` from [ml-explore/mlx-lm#1227](https://github.com/ml-explore/mlx-lm/pull/1227), `patch_mlx_lm_threadlocal_stream.py`, `patch_vllm_mlx_inline_gen.py`. Server flags: `--enable-auto-tool-choice --tool-call-parser hermes` (Ling emits Hermes `<tool_call>{json}</tool_call>`, not Qwen3 XML). Caps at 64K context on M3 Ultra — 128K OOMs. mlx-openai-server incompatible (deeper thread coupling). Re-apply patches 2+3 after `pip install -U vllm-mlx` or `pip install -U mlx-lm`. Full architecture + threading rationale + server-compatibility matrix: [`docs/models/techniques/model-architecture-bailing-hybrid.md`](docs/models/techniques/model-architecture-bailing-hybrid.md).
