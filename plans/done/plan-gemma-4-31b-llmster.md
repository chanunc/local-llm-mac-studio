# Plan: Deploy `lmstudio-community/gemma-4-31B-it-MLX-6bit` on llmster + run all 3 benchmarks

Status: done
Created: 2026-04-30
Completed: 2026-05-01
Canonical: no

> **Implementation:** All five phases shipped 2026-05-01. Model deployed at `~/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit/` (downloaded via `huggingface_hub.snapshot_download` after `lms get` hung at 88% twice — see Phase 5 per-model file for the gotcha). Three benchmarks under `docs/models/benchmarks/gemma-4-31b-it-6bit/`. Per-model file `docs/models/per-model/model-summary-gemma.md` covers both 26B-A4B (migrated from catalog) and 31B-it (new). Headline finding: **6.3× faster browse, 4× faster search vs Qwen3.6-27B on the same llmster** — output 15-23 tok/turn with no thinking-prelude makes Gemma 4 31B-it the new agent-loop champion in `model-benchmark-agent-tool-call.md`.

## Context

The user wants to evaluate Google Gemma 4 31B-it as a candidate model on the **llmster** (LM Studio headless) sidecar already running on the Mac Studio. The repo already documents Gemma 4 26B-A4B (MoE) under `docs/models/model-summary.md`, but the dense 31B-it variant is new. llmster was added 2026-04-30 and is the recommended path for standard-MLX models because its prefill is 3–5× faster than vllm-mlx on OpenCode agent loops; tool-call and reasoning parsing are built into its closed-source MLX runtime, so it is the lowest-friction landing surface for an MLX-native HF release like `lmstudio-community/gemma-4-31B-it-MLX-6bit`.

Outcome: a fully-deployed Gemma 4 31B on llmster with three benchmark JSONs (`api-typical`, `api-tool-test`, `agent-bench` — all `-llmster` suffixed) that slot into the existing `docs/models/benchmarks/` index for direct comparison against `qwen36-27b-6bit/agent-bench-llmster.json` (the closest published anchor on the same server).

**Sync Policy applies:** this triggers **Event 3** (new model) and **Event 4** (three benchmark runs). It does NOT trigger Event 1 (no new server type) and does NOT trigger Event 2 unless the model becomes production primary (it won't — Ling-2.6-flash stays primary).

## Goal

1. Stand up `lmstudio-community/gemma-4-31B-it-MLX-6bit` on llmster on port 1234, alongside the existing Ling primary on port 8000 (no production interruption).
2. Verify `/v1/models` and a one-shot chat completion succeed; capture the actual served-model id (LM Studio mangles HF ids — needs empirical check).
3. Run all three benchmark scripts at 32K context, temperature 0.0 (matches existing `qwen36-27b-6bit` anchor), saving JSON under a new `docs/models/benchmarks/gemma-4-31b-it-6bit/` folder with `-llmster` suffix.
4. Wire the new model into the catalog (`docs/models/model-summary.md`), README Models table, llmster opencode.json `models` map, and the three `model-benchmark-*.md` cross-model tables.

## Questions to answer

1. **Tool-call surface:** does llmster's runtime auto-detect Gemma 4's tool-call format, or does it leak raw XML/text into `content`? llmster claims runtime-level parser detection — Gemma 4 emits a different format from Qwen3.x; this is the key unknown.
2. **Reasoning routing:** does Gemma 4's `<think>…</think>` (it has built-in thinking) get routed to `reasoning_content`, dumped into `content`, or ignored?
3. **Throughput:** what TTFT / prefill tok/s / decode tok/s does dense 31B at 6-bit hit on M3 Ultra at 32K context? (Anchor: 27B-6bit on llmster is 47K tok/s prefill @ 32K, ~0.7s flat TTFT.)
4. **Agent-loop wall time:** how does Gemma 4 31B on llmster compare to Qwen3.6-27B on llmster on the standard `bench_agent_tool_call.py` browse + Hackernews scenarios?

## Non-goals

- No production switch — Ling-2.6-flash stays primary on vllm-mlx:8000.
- No new client config beyond `configs/clients/llmster/opencode.json` (per llmster's provisional posture in CLAUDE.md).
- No vision-input testing — gemma-4-31b-it is text-only per HF card.
- No multi-server cross-comparison this round (no oMLX or mlx-openai-server runs); Gemma 4 has known parser issues on those (`docs/models/model-summary.md` Gemma 4 26B caveats).
- No re-quantization, no fine-tune.

## Methodology

**Server isolation.** llmster on 1234 is already up if the box is in its standard state. Loading gemma-4-31b-it does NOT require restarting the server — `lms load` is an in-process operation. Ling on 8000 stays untouched.

**Disk.** 31B at 6-bit ≈ 25–27 GB. Verify ≥ 35 GB free before `lms get` (note: `lms get` does not dedup with the HF cache, so this is fresh allocation). If short, the recovery move is to unload non-essential llmster models, not to touch the production primary.

**Comparability gates.**
- Context length: `--context-length 65536` at load time (matches Qwen3.6-27B llmster anchor; 32K is the bench target with headroom).
- Benchmark contexts: `512,4096,8192,32768` for `bench_api_server.py` (matches existing JSON schema in `qwen36-27b-6bit/api-server-llmster.json`).
- Temperature 0.0, `--runs 3 --warmup 1` for `bench_api_server.py`; defaults for the other two scripts.

**Slug.** `gemma-4-31b-it-6bit` (lowercase, hyphenated, matches `qwen36-27b-6bit` style).

**Served-model id capture.** Post-load, `curl -s http://<MAC_STUDIO_IP>:1234/v1/models | jq -r '.data[].id'` is the source of truth for `--model` in bench scripts and for the opencode.json `models` map key. LM Studio mangling (org-prefix-stripped, lowercased) means it will likely be `gemma-4-31b-it` — but capture, don't assume.

## Phase 1 — Pre-flight (read-only)

1. SSH to macstudio, verify llmster is up: `~/.lmstudio/bin/lms server status` and `curl -s http://localhost:1234/v1/models`.
2. Verify free disk: `df -h ~/.lmstudio/models | tail -1` — need ≥ 35 GB free.
3. Confirm Ling primary still healthy: `curl -s http://localhost:8000/v1/models`.
4. Confirm the HF model exists at the URL the user provided. (`lms get` resolves HF URLs; if the repo is gated/missing, `lms get` will fail loudly.)
5. Verify benchmark scripts are executable on the bench host (MacBook): `python3 scripts/bench/bench_api_server.py --help`, etc.

## Phase 2 — Deploy on llmster

1. Download the model:
   ```bash
   ssh macstudio "~/.lmstudio/bin/lms get \
     'https://huggingface.co/lmstudio-community/gemma-4-31B-it-MLX-6bit' -y"
   ```
2. Load into the running server with explicit context:
   ```bash
   ssh macstudio "~/.lmstudio/bin/lms load 'gemma-4-31b-it' \
     --gpu max --context-length 65536 -y"
   ```
   (If the load-time id differs from `gemma-4-31b-it`, the `lms get` step will print the actual id; use that.)
3. Capture the served id:
   ```bash
   ssh macstudio "curl -s http://localhost:1234/v1/models | python3 -m json.tool"
   ```
   Record the returned `id` — call it `<SERVED_ID>` for the rest of this plan.

## Phase 3 — Smoke test

1. One-shot chat completion (no tools) — confirms the model generates and reasoning routing:
   ```bash
   curl -s http://<MAC_STUDIO_IP>:1234/v1/chat/completions \
     -H 'Content-Type: application/json' \
     -d '{"model":"<SERVED_ID>","messages":[{"role":"user","content":"In one short sentence, what is MLX?"}],"max_tokens":80,"stream":false}' \
     | python3 -m json.tool
   ```
   Inspect: does `choices[0].message.reasoning_content` exist? Does `content` contain `<think>` tags (red flag — same bug shape as vmlx pre-patch)?
2. Tool-call probe — single function call. If llmster's runtime does not auto-detect Gemma 4's tool-call format, this will return `tool_calls: null` and emit raw text. That is a finding to record for question 1, not a deployment failure.
3. Stop here if Phase 2/3 reveals the model can't chat at all (corrupt download, runtime extension can't load gemma-4 arch). Otherwise proceed.

## Phase 4 — Benchmarks

Run from the MacBook (this repo's working directory). All three target the llmster endpoint and the Phase-2-captured `<SERVED_ID>`. Output dir is created on first run.

### 4a — Direct call (`bench_api_server.py`)

```bash
mkdir -p docs/models/benchmarks/gemma-4-31b-it-6bit
python3 scripts/bench/bench_api_server.py \
  --base-url http://<MAC_STUDIO_IP>:1234/v1 \
  --model <SERVED_ID> \
  --contexts 512,4096,8192,32768 \
  --max-tokens 50 --runs 3 --warmup 1 \
  --output docs/models/benchmarks/gemma-4-31b-it-6bit/api-server-llmster.json
```

### 4b — API tool call (`bench_api_tool_call.py`)

```bash
python3 scripts/bench/bench_api_tool_call.py \
  --base-url http://<MAC_STUDIO_IP>:1234/v1 \
  --model <SERVED_ID> \
  --output docs/models/benchmarks/gemma-4-31b-it-6bit/api-tool-test-llmster.json
```

If Phase 3 step 2 shows tool calls don't fire on llmster for Gemma 4, still run this — the JSON's `tool_calls: []` and `finish_reason` fields are the evidence we want for question 1.

### 4c — Agent tool call (`bench_agent_tool_call.py`)

This script invokes `opencode run --format json` and reads opencode's config. Two paths:
- **Preferred:** point opencode at gemma-4-31b temporarily by editing `~/.config/opencode/opencode.json` (or whatever the active local opencode config is) to set `"model": "macstudio/gemma-4-31b-it"` AND adding the matching `models` entry. After the run, revert.
- **Alternative:** if `bench_agent_tool_call.py` accepts a model-override flag (verify with `--help`), use it directly without touching the global config.

```bash
python3 scripts/bench/bench_agent_tool_call.py \
  --scenario both --warmup 1 --runs 3 \
  --output docs/models/benchmarks/gemma-4-31b-it-6bit/agent-bench-llmster.json
```

If 4b shows zero tool calls fire, 4c will likely fail or be meaningless — record `error_count` and skip rather than retry. This is itself an answer to question 1.

## Phase 5 — Documentation sync (Event 3 + Event 4)

### Event 3 — new model (`docs/models/model-summary.md`)

Add an Index entry (alphabetical, near the existing Gemma 4 26B-A4B Index line at `model-summary.md:9` — the per-model section anchor `#gemma-4-26b-a4b-4-bit` at `model-summary.md:298`) and a per-model section with the standard spec table:

| Field | Value |
|:--|:--|
| Base Model | `google/gemma-4-31b-it` |
| MLX variant | `lmstudio-community/gemma-4-31B-it-MLX-6bit` |
| Format | MLX safetensors |
| Vendor | Google (LM Studio Community quant) |
| Architecture | Dense (not MoE — distinct from 26B-A4B) |
| Parameters | 31B |
| Density | dense |
| Quantization | 6-bit |
| Specialties | (fill from HF card — likely text-only, multilingual, reasoning-capable) |
| Tokens/sec | (from Phase 4a results) |
| On-disk size | (from `du -sh ~/.lmstudio/models/lmstudio-community/...`) |
| Context Size | 65536 (loaded) / native (per HF card) |
| License | Gemma Terms of Use |
| Key Features | (from HF card) |

Server config block: llmster on 1234, no parser flags (built-in detection). Caveats: list whatever Phase 3/4 surfaces (tool-call success/failure, reasoning routing, anything weird).

### Event 3 — supporting files

- `docs/models/per-model/model-summary-gemma.md` — **default: create**. Post-2026-05-01 the catalog convention flipped: every recently added family (Qwen3.5/3.6/Coder/Nemotron/Ling/MiMo) lives in `per-model/` with the catalog reduced to a stub linking out (see `model-summary.md:10-17`). Create a single Gemma-family per-model file covering both 26B-A4B (migrate the existing inline section at `model-summary.md:298-365` — Gemma 4 26B is the last inline holdout from the old structure) and the new 31B-it. The catalog `model-summary.md` Gemma entry then collapses to a one-line stub matching the Qwen3.6 pattern at `model-summary.md:15`. Skip the migration of the 26B section only if Phase 4 surfaces nothing surprising AND the 31B entry fits in <100 lines — in that case keep 31B inline next to the existing 26B section, and capture this as a deviation in the verification step.
- `docs/models/README.md` — add a Per-model deep dives row for `model-summary-gemma.md` (if created per the default above).
- `README.md` Models table — one row near the existing Gemma 4 26B-A4B row: `[Gemma 4 31B-it (6-bit)](docs/models/model-summary.md#gemma-4-31b-it-6-bit) | Dense 31B | <tps from 4a> | 64K | <best for: …>`.
- `configs/clients/llmster/opencode.json` — add to `models` map:
  ```json
  "gemma-4-31b-it": {
    "name": "Gemma 4 31B-it 6bit (llmster, standard MLX)",
    "tools": <true if 4b shows tool calls fire, else false>,
    "reasoning": <true if Phase 3 shows reasoning_content populated, else false>,
    "limit": { "context": 65536, "output": 4096 }
  }
  ```
  Do NOT change the top-level `model` / `small_model` keys (Qwen3.6-27B remains the default for opencode.json).
- `docs/current.md` — **no change** (Gemma 4 31B is not promoted to sidecar/fallback; it's an additional llmster-loaded option). Only add it here if it earns one of those slots.

### Event 4 — benchmarks

- `docs/models/benchmarks/gemma-4-31b-it-6bit/api-server-llmster.json` — produced in 4a.
- `docs/models/benchmarks/gemma-4-31b-it-6bit/api-tool-test-llmster.json` — produced in 4b.
- `docs/models/benchmarks/gemma-4-31b-it-6bit/agent-bench-llmster.json` — produced in 4c.
- `docs/models/benchmarks/model-benchmark-api-server.md` — append a row to the cross-model table; add per-model results section linking the JSON.
- `docs/models/benchmarks/model-benchmark-agent-tool-call.md` — append a row; add per-model results section linking the JSON. If 4b/4c failed (no tool calls), record the failure mode in the row rather than omitting.
- `docs/models/benchmarks/model-benchmark-standalone.md` — only update if Phase 4a establishes a new fastest/slowest extreme on dense 30B-class MLX.
- `docs/models/README.md` Benchmarks table — **no change** (no new benchmark *type* introduced).
- `README.md` Benchmarks section — only update if Phase 4 establishes a new fastest/slowest extreme worth surfacing on the front page.

## Critical files to modify

- `configs/clients/llmster/opencode.json` (add model entry to `provider.macstudio.models` map; do NOT change top-level `model` / `small_model` — Qwen3.6-27B stays default)
- `docs/models/model-summary.md` (collapse Gemma 4 26B-A4B inline section to a family stub; add stub link for 31B-it under the same family entry — see Event 3 supporting files)
- `docs/models/per-model/model-summary-gemma.md` (NEW — covers 26B-A4B migrated from catalog + 31B-it from this run; default per current convention)
- `docs/models/README.md` (add Per-model deep dives row for `model-summary-gemma.md`)
- `README.md` (add Models table row near the existing 26B-A4B row at `README.md:217`)
- `docs/models/benchmarks/gemma-4-31b-it-6bit/{api-server-llmster,api-tool-test-llmster,agent-bench-llmster}.json` (new dir + 3 files)
- `docs/models/benchmarks/model-benchmark-api-server.md` (add row + section)
- `docs/models/benchmarks/model-benchmark-agent-tool-call.md` (add row + section)

Reused (no edits):
- `scripts/bench/bench_api_server.py`, `scripts/bench/bench_api_tool_call.py`, `scripts/bench/bench_agent_tool_call.py`
- `docs/servers/llmster/summary.md` (no server change)
- `docs/current.md` (no production change)

## Verification

1. **Health:** `curl -s http://<MAC_STUDIO_IP>:1234/v1/models | jq -r '.data[].id'` lists the gemma-4 served id and the existing Qwen3.6-27B (no regression).
2. **Generation:** the Phase 3 one-shot chat returns coherent text and a sane `finish_reason: stop`.
3. **Bench JSONs:** all three files exist under `docs/models/benchmarks/gemma-4-31b-it-6bit/` and parse with `python3 -m json.tool`.
4. **Sync drift sweep** (CLAUDE.md pre-commit check):
   ```bash
   grep -n "gemma-4-31b\|gemma-4-31B" README.md AGENTS.md CLAUDE.md \
     configs/README.md docs/current.md docs/models/model-summary.md \
     configs/clients/llmster/opencode.json
   ```
   Every doc that mentions the new model should be in sync; no doc should mention an old/wrong served id.
5. **OpenCode end-to-end** (optional, light): with `configs/clients/llmster/opencode.json` updated, run a single `opencode run` against `macstudio/gemma-4-31b-it` and confirm a tool-using prompt either succeeds or fails consistent with Phase 3 step 2.
6. **Production untouched:** Ling-2.6-flash on vllm-mlx:8000 still serves throughout — `curl -s http://<MAC_STUDIO_IP>:8000/v1/models` returns the Ling id at every checkpoint.

## Risks and decisions

- **Risk: tool calls don't fire on llmster for Gemma 4.** llmster's "built-in parser detection" was validated for Qwen3.x; Gemma 4 uses a different tool-call surface (Gemma's chat template emits a distinct format). If 4b returns zero tool_calls, that is the answer to question 1 — record it in `model-summary.md` caveats, set `"tools": false` in opencode.json, and skip 4c rather than burn cycles. **No retry-with-different-server in this plan** — that would be a follow-up plan.
- **Risk: disk pressure.** If `lms get` fills the volume, the Phase-1 disk check should catch it. Recovery: `~/.lmstudio/bin/lms unload <other-llmster-model>` and `lms ls` to see what else is resident; do NOT touch `~/vllm-mlx-env/` or `~/.cache/huggingface/` (those belong to the production primary's deps).
- **Risk: served-model-id mismatch.** Always re-derive `<SERVED_ID>` from `/v1/models` before benching. Hardcoding `gemma-4-31b-it` and getting it wrong wastes a full bench run.
- **Risk: opencode global config edit for 4c.** If you edit `~/.config/opencode/opencode.json` for the agent-bench run, revert after — leaving it pointed at gemma-4 silently changes interactive opencode behavior next session. Better: confirm `bench_agent_tool_call.py --help` for a model override, prefer that.
- **Decision: provisional posture.** Per llmster precedent, only `opencode.json` is updated under `configs/clients/llmster/`. Do not backfill `claude-code-settings.json`, `pi-models.json`, `openclaw-provider.json`, `qwen-code-settings.json` for this model — that is reserved for if/when Gemma 4 31B graduates to a permanent role.
- **Decision (revised 2026-05-01): per-model deep-dive file IS the default.** The 2026-05-01 family-split refactor (commit `34e08c5`) moved Qwen3.5/3.6/Coder/Nemotron into `per-model/` and reduced their catalog entries to stubs. Gemma 4 26B-A4B is now the last inline holdout. Add `docs/models/per-model/model-summary-gemma.md` covering both 26B-A4B (migrated from `model-summary.md:298-365`) and the new 31B-it. Spin out skipped only if Phase 4 findings are unremarkable AND 31B fits inline in <100 lines next to 26B — record any deviation in the Verification section.

## Plan-lifecycle (Event 6) afterwards

When Phases 1–5 are complete and merged: `git mv plans/active/plan-gemma-4-31b-llmster.md plans/done/`, link this plan from any commit message that references it, and move the row in `plans/README.md` from Active to Done.
