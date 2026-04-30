# Plan: Deploy dflash-mlx with Qwen3.6-35B-A3B target + DFlash drafter

Status: done (2026-04-30)
Created: 2026-04-30
Canonical: no

## Implementation

- Runbook: [`docs/servers/dflash-mlx/summary.md`](../../docs/servers/dflash-mlx/summary.md)
- Patches: [`scripts/patches/patch_dflash_mlx_serve.py`](../../scripts/patches/patch_dflash_mlx_serve.py), [`scripts/patches/patch_mlx_lm_match.py`](../../scripts/patches/patch_mlx_lm_match.py), [`scripts/patches/patch_dflash_mlx_host.py`](../../scripts/patches/patch_dflash_mlx_host.py) (0.1.0 only)
- Bench JSONs: [`docs/models/benchmarks/qwen36-35b-a3b-4bit/`](../../docs/models/benchmarks/qwen36-35b-a3b-4bit/)
- Cross-model summary: [`docs/models/benchmarks/model-benchmark-api-tool-call.md`](../../docs/models/benchmarks/model-benchmark-api-tool-call.md) (new)
- Catalog entry: [`docs/models/per-model/model-summary-qwen-3-6.md` § Qwen3.6-35B-A3B (4-bit)](../../docs/models/per-model/model-summary-qwen-3-6.md#qwen36-35b-a3b-4-bit)
- Client config: [`configs/clients/dflash-mlx/opencode.json`](../../configs/clients/dflash-mlx/opencode.json) (provisional, OpenCode-only)
- Production primary unchanged (still Ling-2.6-flash on `vllm-mlx` :8000); dflash-mlx runs as a sidecar on :8098.

## Phase progress (2026-04-30)

- **Phase 1** (pre-flight): ✅ done. `~/dflash-mlx-env/` Python 3.11.15 + `dflash-mlx 0.1.0` + `mlx 0.31.2` + `mlx-lm 0.31.3`. Host-binding patch script `scripts/patches/patch_dflash_mlx_host.py` written and applied (binds 0.0.0.0 instead of 127.0.0.1). Pre-download succeeded: target 19 GB, drafter 905 MB; 105 GB free disk after reclaiming 80 GB by deleting `models--jedisct1--MiMo-V2.5-MLX-4bit-first130experts-qhead`.
- **Phase 2** (library smoke): ✅ done. `mlx-community/Qwen3.6-35B-A3B-4bit` (model_type `qwen3_5_moe`, multimodal wrapper) loads in 1.1s; `z-lab/Qwen3.6-35B-A3B-DFlash` loads as `DFlashDraftModel` in 0.1s. Generation: 128 tokens / 4.85s, **86.7% draft acceptance** (111/128 from drafter), coherent reasoning-trace output. Smoke logs at `/tmp/dflash-smoke-stage{1,2}.log` on macstudio.
- **Phase 3** (HTTP server smoke, reduced): ✅ done with PyPI 0.1.0 (serve.py is custom HTTPServer, no tools[]). After Phase 4 prep, **upgraded to 0.1.4.1 from main branch** (`pip install git+https://github.com/bstnxbt/dflash-mlx.git`) which **wraps `mlx_lm.server`** and exposes full tool-calling, sampling controls, prompt cache. Required two patches against upstream: (a) `default_model_map → _model_map` typo in DFlashModelProvider.load(), (b) startup banner falls back to `cli_args.draft_model` when `model_key` isn't yet set (lazy-load ordering). Tool-call smoke against 0.1.4.1: clean OpenAI `tool_calls[]` array, `finish_reason: "tool_calls"`, separate `message.reasoning` field — no leak into `content`.
- **Phase 4** (benchmarks, revised scope): ✅ all three benches landed at `docs/models/benchmarks/qwen36-35b-a3b-4bit/`. Required one additional patch: `mlx_lm.generate.match()` `KeyError: None` upstream bug — when the tool-detection state machine reaches a terminal state, `s` becomes None and the next call fails. Fixed by resetting to initial state when `s is None`. Three benches passed cleanly post-patch.

## Phase 4 — Benchmark headline numbers (Qwen3.6-35B-A3B-4bit + Qwen3.6-35B-A3B-DFlash drafter)

| Bench | Result |
|---|---|
| **api-server** (`bench_api_server.py`) | ctx=512 → ctx=32K: gen 89.5 → 74.1 tok/s, prefill 1,366 → 837 tok/s, TTFT 0.39s → 39.2s. Decode rate stays >74 tok/s even at 32K context (DFlash effective). |
| **api-tool-call** (`bench_api_tool_call.py`) | 5/5 single-call scenarios pass with clean `tool_calls[]`, latencies 1.68-6.08s. 3-turn multi-turn loop (read_file → write_file → final): 5.9s total. |
| **agent-bench** (`bench_agent_tool_call.py` via OpenCode) | Browse: **27.59s** wall median (vs llmster on Qwen3.6-27B-6bit: 31.96s — **13% faster**). Search: 54.78s wall median (vs llmster: 25.71s — **2.1× slower** because 3-turn loop with growing context favors prefill, and DFlash's win is decode-side). |

**Comparison anchors active in repo:**
- `qwen36-27b-6bit/agent-bench-llmster.json` — llmster on smaller dense sibling (cross-server headline)
- `qwen36-35b-a3b-jangtq4-crack/agent-bench.json` — same base on vmlx + JANGTQ4 (different runtime + uncensoring)
- `qwen36-35b-a3b-6bit/api-server-mlx-openai-server.json` — same family at 6-bit on mlx-openai-server (same-stack autoregressive baseline)

## Required upstream patches (record for the runbook)

Three local patches to make the stack work — all idempotent, must be re-applied after each upgrade of the relevant package:

1. **`scripts/patches/patch_dflash_mlx_host.py`** — `dflash-mlx 0.1.0` only: bind 127.0.0.1 → 0.0.0.0 (resolved natively in 0.1.4.1's `--host` flag).
2. **`dflash-mlx 0.1.4.1` `serve.py`** — two upstream bugs:
   - `DFlashModelProvider.load()` references `self.default_model_map` (doesn't exist on `mlx_server.ModelProvider`) → must be `self._model_map`.
   - `_print_startup_banner()` requires `model_key` resolved before banner prints, but model is lazy-loaded → fall back to `cli_args.draft_model` for the banner.
3. **`mlx-lm 0.31.3` `generate.py`** — `match()` static method blows up with `KeyError: None` when the tool-detection state machine post-terminal `s` is None. Fix: when `s is None` at entry, reset to initial state.

Bench-script enhancements (committed, broadly useful):
4. **`scripts/bench/bench_api_server.py`** — also recognize `delta.reasoning` (mlx-lm naming) in addition to `delta.content` / `delta.reasoning_content` for TTFT detection.
5. **`scripts/bench/bench_agent_tool_call.py`** — new `--base-url` flag overrides `discover_config()` health-check URL.

## Findings from Phase 1-2 (overrides assumptions in steps below)

1. **Actual CLI entrypoints** are `dflash`, `dflash-serve`, `dflash-benchmark` (not `dflash-mlx` / `dflash-mlx-openai-server` as originally drafted). `dflash-benchmark` has built-in baseline-vs-DFlash matrix mode with thermal cooldown — could supplement `bench_api_server.py` in Phase 4.
2. **`dflash-serve` flag set:** `--model MODEL`, `--draft DRAFT` (optional override), `--port PORT`, `--no-chat-template`. **No `--host` flag** — original 0.1.0 binds 127.0.0.1 hardcoded. Fixed by `scripts/patches/patch_dflash_mlx_host.py` (re-apply after every `pip install -U dflash-mlx`).
3. **`DRAFT_REGISTRY` in dflash-mlx 0.1.0 has no Qwen3.6 entries** — only Qwen3.5 family. Must always pass `--draft z-lab/Qwen3.6-35B-A3B-DFlash` explicitly. The architecture itself works (Phase 2 confirmed); only the auto-resolve map is stale.
4. **Library API:** `dflash_mlx.generate.{load_target_bundle, load_draft_bundle, stream_dflash_generate}` (not `dflash.model_mlx.{load, load_draft, stream_generate}` as in the upstream z-lab README). Stream events are typed: `prefill` (1×), `token` (N×), `summary` (1× — has `phase_timings_us` dict + `acceptance_ratio` perfect for benchmark capture).
5. **`mlx-community/Qwen3.6-35B-A3B-4bit` is a multimodal MoE checkpoint** (`Qwen3_5MoeForConditionalGeneration` arch, `image_token_id: 248056`, weights nested under `language_model.*`). dflash-mlx handles it via `_target_text_wrapper` which unwraps `target_model.language_model` automatically. Benchmarks should treat this as text-only — dflash-serve doesn't expose a vision input path anyway.
6. **`dflash-serve 0.1.0` has no OpenAI tool-call surface.** `do_POST /v1/chat/completions` reads only `model`, `messages`, `max_tokens`, `stream`. It does **not** process `tools[]`, `tool_choice`, `temperature` (always greedy via `mx.argmax`), `top_p`, `top_k`, `response_format`, or `stop` strings. Streaming emits `delta.content` text only — no `tool_calls[]` deltas. Reasoning blocks (`<think>…</think>`) land verbatim in `content`. **This invalidates the original Phase 3 tool-call smoke and Phase 4b/4c benchmarks at the server layer regardless of the underlying model's capability.**

## Revised scope after Finding 6

Originally the plan tested three benchmark types (api-server, api-tool-call, agent-tool-call). Two of those depend on tool-calling support that `dflash-serve` does not expose. Revised scope:

- **Phase 3** — drop `tools[]`/agentic smoke; keep a minimal plain-prompt SSE-streaming smoke (server starts, `/v1/models` responds, `/v1/chat/completions` streams a coherent completion) and a reasoning-leak observation (informational, not pass/fail).
- **Phase 4a** — keep `bench_api_server.py` (raw prefill/decode throughput, no tool calls). This is the headline number for Q2 (does DFlash speedup translate to M3 Ultra).
- **Phase 4b (api-tool-call) + 4c (agent-bench)** — **dropped at the server layer**. dflash-serve cannot emit `tool_calls[]`. To answer Q1/Q3 we'd either need to (a) extend `serve.py` with a tool-call parser shim, or (b) write a custom harness on top of `stream_dflash_generate`. Both are out of the original plan's scope and effectively turn this into a fork-and-extend project. Recommendation: defer.
- **Phase 4d** — replace with `dflash-benchmark` matrix run (built-in baseline-vs-DFlash A/B with thermal cooldown), which is what the bstnxbt project itself ships for this exact use case. Cleaner numbers than rolling our own.

**Implication for the eventual `docs/servers/dflash-mlx/summary.md`:** the headline Known Limitation is "research-grade decode-throughput server only — no OpenAI tool-call surface, no temperature/sampling controls, fixed greedy decoding." Provisional posture (llmster precedent) is even more justified here than originally framed.

## Context

`z-lab/Qwen3.6-27B-DFlash` cannot run on the Mac Studio: the upstream DFlash MLX backend, the `dflash-mlx` PyPI package (bstnxbt), the Aryagm fork, and `ddtree-mlx` all enumerate supported target+drafter pairs and **none** include `Qwen3.6-27B`. The HuggingFace card itself only documents vLLM/SGLang via custom upstream PRs and warns "inference engine support may not be fully available yet due to architectural changes" (causal SWA layers in the Qwen3.6-27B hybrid stack). The Apple-Silicon vLLM fork (`vllm-mlx 0.2.6`) does not pick up upstream vLLM PRs and has no FlashAttention path.

The closest deployable DFlash target on Apple Silicon is **`mlx-community/Qwen3.6-35B-A3B-4bit` + `z-lab/Qwen3.6-35B-A3B-DFlash`** via `pip install dflash-mlx`. It is the largest Qwen3.6-family pair on the dflash-mlx supported list and the project's README explicitly says it is "Optimized for Qwen3.5 / Qwen3.6 models (hybrid GatedDeltaNet + attention architecture)." DFlash itself reports up to **2.9× speedup at concurrency=1 on Math500** with `block_size=16`; the r/LocalLLaMA Apple-Silicon writeup measured `Qwen3.5-9B` going from 53.74 → 219.83 tok/s on an M5 Max (89% draft acceptance).

**Sync Policy applies.** This plan triggers **Event 1 (new server type)** for the `dflash-mlx-openai-server` daemon, **Event 3 (new model)** for `mlx-community/Qwen3.6-35B-A3B-4bit` if not already in `docs/models/model-summary.md`, **Event 4 (benchmark)** for each of the three bench runs in Phase 4, **Event 5 (script)** if a launch wrapper lands under `scripts/`, and **Event 6 (plan lifecycle)** when this plan moves to `plans/done/`. Phase 5 below is written against those checklists; do not skip "minor" docs.

llmster precedent (added 2026-04-30) applies for provisional status: client configs are deferred to `opencode.json` only until the server demonstrates sustained production use.

## Goal

Stand up dflash-mlx as a sidecar server on the Mac Studio, verify tool-call correctness end-to-end, and produce three benchmark JSONs that slot directly into the existing `docs/models/benchmarks/<model-slug>/` index so they're directly comparable to the on-disk anchors:

- `qwen36-35b-a3b-6bit/api-server-mlx-openai-server.json` — same family, mlx-openai-server, 6-bit autoregressive
- `qwen36-35b-a3b-jangtq4-crack/agent-bench.json` — same base, vmlx, JANGTQ4 2-bit
- `qwen36-27b-6bit/agent-bench-llmster.json` — llmster on the smaller dense sibling (overall headline server-vs-server number)

## Questions to answer

1. Does dflash-mlx's `dflash-mlx-openai-server` correctly emit `tool_calls[]` in the OpenAI-streaming response, or does the closed-source draft+verify path leak raw `<tool_call>…` XML into `content` like vmlx pre-patch did?
2. What is the realised speedup of `Qwen3.6-35B-A3B + DFlash` on M3 Ultra vs. plain autoregressive `Qwen3.6-35B-A3B-6bit` on mlx-openai-server (concurrency=1, agent-loop wall time)?
3. Does the dflash-mlx server hold up under the agent-bench's multi-tool, 3+ turn conversation (where draft acceptance typically falls off and verification cost dominates)?
4. Are reasoning tokens (`<think>…</think>` blocks emitted by Qwen3.6) routed to `reasoning_content` or dumped into `content`? The DFlash README has no parser-flag concept.
5. Does the closed-source MLX kernel pin to a specific `mlx` version that conflicts with the `vllm-mlx-env` venv? (Resolved by using a **separate venv** `~/dflash-mlx-env/`.)

## Non-goals

- Not benchmarking concurrency > 1 — DFlash's primary win is at concurrency=1; multi-stream interactive-server behaviour is out of scope.
- Not integrating dflash-mlx into `scripts/switch_opencode_config.py` until it earns permanent status (Event 1 deferred-templates rule, mirrors llmster's provisional posture).
- Not wiring an Anthropic-API shim — the dflash-mlx server is OpenAI-only, same as llmster.
- Not testing image input — `dflash-mlx-openai-server` is documented "text-only message content; no image input."
- Not attempting `z-lab/Qwen3.6-27B-DFlash` (covered in the Context section above).
- Not retraining or fine-tuning the drafter; we use `z-lab/Qwen3.6-35B-A3B-DFlash` as published.

## Methodology

**Server isolation.** Install dflash-mlx in a fresh venv `~/dflash-mlx-env/` to avoid mlx-version conflicts with `~/vllm-mlx-env/` and `~/mlx-openai-server-env/`. Bind the server to its default port `8098` (NOT 8000) so vllm-mlx can stay live on 8000 throughout Phase 2 — only stop the production primary for the bench phase, then restart it.

**Port discipline.**
- Production: `vllm-mlx` on `8000` (Ling-2.6-flash) — keep up during install/smoke (Phase 1-2), stop only for Phase 4 bench.
- New: `dflash-mlx` on `8098`.
- All bench scripts already accept `--base-url` per the `agent-bench-llmster.json` precedent at port 1234.

**Comparability gates.** All three benchmarks (`bench_api_server.py`, `bench_api_tool_call.py`, `bench_agent_tool_call.py`) run against the same target weights at the same context length (32K) at temperature 0.0 (matches the existing 27B-6bit and 35B-A3B-6bit anchor JSONs). DFlash-specific knobs:
- `block_size=16` (the dflash-mlx README default; matches the MLX upstream tested config).
- `num_speculative_tokens=15` (vLLM card default; the MLX server may or may not expose this — record actual).
- `sliding_window_size=None` for the smoke-test pass; revisit only if KV growth becomes a problem at 32K context.

**Smoke test scope.** Three scenarios before any bench:
1. Single-shot tool call: 1 tool, 1 turn (tests OpenAI tool_calls[] emission).
2. Agentic 3-turn: tool → tool result → second tool → final answer (tests stop/restart of speculative decoding across tool-call boundaries).
3. Reasoning visibility: prompt that triggers `<think>` block; verify it lands in `reasoning_content`, not `content`.

**Production-impact gate.** If smoke fails on (1), abort Phase 4 and document the failure under Known Limitations in the runbook — DFlash is research-grade, this is an acceptable outcome for a sidecar evaluation.

## Implementation steps

### Phase 1 — Pre-flight (1 hr, no production impact)

1. **Disk budget check.** Target weights `mlx-community/Qwen3.6-35B-A3B-4bit` ≈ 22 GB, drafter `z-lab/Qwen3.6-35B-A3B-DFlash` ≈ 1 GB. ~23 GB into `~/.cache/huggingface/hub/`. Confirm free space: `ssh macstudio "df -h ~/.cache/huggingface/"`.
2. **Create venv.** `ssh macstudio "python3.11 -m venv ~/dflash-mlx-env && ~/dflash-mlx-env/bin/pip install -U pip"`.
3. **Install dflash-mlx.** `ssh macstudio "~/dflash-mlx-env/bin/pip install dflash-mlx"`.
4. **Verify imports** without downloading the model: `ssh macstudio "~/dflash-mlx-env/bin/python -c 'from dflash.model_mlx import load, load_draft, stream_generate; print(\"ok\")'"`.
5. **Verify CLI entrypoints** are on PATH inside the venv: `~/dflash-mlx-env/bin/dflash-mlx --help` and `~/dflash-mlx-env/bin/dflash-mlx-openai-server --help`.
6. **Pre-download** to surface any HF auth / network issues before the bench: `ssh macstudio "HF_HUB_ENABLE_HF_TRANSFER=1 ~/dflash-mlx-env/bin/python -c 'from huggingface_hub import snapshot_download; snapshot_download(\"mlx-community/Qwen3.6-35B-A3B-4bit\"); snapshot_download(\"z-lab/Qwen3.6-35B-A3B-DFlash\")'"`.

### Phase 2 — Library smoke test (30 min, no production impact)

7. **Library-mode smoke** with `stream_generate`:
    ```python
    from dflash.model_mlx import load, load_draft, stream_generate
    model, tok = load("mlx-community/Qwen3.6-35B-A3B-4bit")
    draft = load_draft("z-lab/Qwen3.6-35B-A3B-DFlash", sliding_window_size=None)
    msgs = [{"role": "user", "content": "Write a quicksort in Python."}]
    prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=True)
    for r in stream_generate(model, draft, tok, prompt, block_size=16, max_tokens=512):
        print(r.text, end="", flush=True)
    ```
8. **Capture** total wall time, tokens emitted, and a sample of `r` fields (does the result include draft acceptance rate? per-block timing?). Save the smoke transcript to `/tmp/dflash-smoke-stage1.log` for the runbook.

### Phase 3 — HTTP server smoke test (1 hr, no production impact — different port)

9. **Start the OpenAI server** (post-patch, binds 0.0.0.0; `--draft` is REQUIRED for Qwen3.6 since `DRAFT_REGISTRY` only knows Qwen3.5):
    ```bash
    ssh macstudio "nohup ~/dflash-mlx-env/bin/dflash-serve \
      --port 8098 \
      --model mlx-community/Qwen3.6-35B-A3B-4bit \
      --draft z-lab/Qwen3.6-35B-A3B-DFlash \
      > /tmp/dflash-mlx.log 2>&1 &"
    ```
    Verify: `curl -s http://<MAC_STUDIO_IP>:8098/v1/models | python3 -m json.tool` (the dflash-serve HTTPServer may not expose `/health` — confirm endpoint set during smoke).
10. **(Dropped — see Finding 6.)** Tool-call smoke is moot: `dflash-serve` does not process `tools[]` or emit `tool_calls[]` deltas. The smoke would deterministically fail at the server layer regardless of model capability.
11. **(Dropped — see Finding 6.)** Agentic multi-turn smoke depends on tool_calls[] in the streaming response.
12. **Smoke — plain prompt + reasoning observation**: POST a non-streaming and a streaming `/v1/chat/completions` with a single `messages=[{"role":"user","content":"…"}]`. Verify (a) non-stream returns `choices[0].message.content` with sensible text, (b) stream emits `delta.content` SSE chunks ending with `[DONE]`, (c) note whether the model emits `<think>…</think>` literals into `content` (expected — informational only, will be a documented Known Limitation).
13. **Decision gate.** If the plain smoke fails (server crashes, returns 5xx, or emits gibberish), abort Phase 4 and document the failure mode in a draft `docs/servers/dflash-mlx/summary.md` Known Limitations entry.

### Phase 4 — Benchmarks (2 hrs, REQUIRES production downtime)

Production primary (`vllm-mlx` running Ling-2.6-flash on port 8000) shares the M3 Ultra's 96 GB unified memory pool. Ling alone uses ~80 GB; dflash-mlx target+drafter+KV ≈ 25-30 GB. Co-residency is too tight for stable benchmark numbers. **Stop vllm-mlx** for the duration of Phase 4 only.

14. **Capture restore command** before stopping production:
    ```bash
    ssh macstudio "ps -axo command= | grep -E 'vllm-mlx serve' | grep -v grep" > /tmp/ling-restore.cmd
    ```
15. **Stop production**: `ssh macstudio "pkill -f vllm-mlx"`.
16. **Re-confirm dflash-mlx is healthy** after the kill: `curl -s http://<MAC_STUDIO_IP>:8098/health`.

#### 4a — API server bench

17. Run `scripts/bench/bench_api_server.py` against the dflash-mlx server. Expect a `--base-url http://<MAC_STUDIO_IP>:8098/v1` flag (mirrors `agent-bench-llmster.json`'s precedent at port 1234). Save output to:
    ```
    docs/models/benchmarks/qwen36-35b-a3b-4bit/api-server-dflash-mlx.json
    ```
18. Compare against the existing `qwen36-35b-a3b-6bit/api-server-mlx-openai-server.json` baseline. Same family, slightly different quant (4-bit MLX vs 6-bit MLX). Headline numbers expected: prefill tok/s, decode tok/s, time-to-first-token.

#### 4b — API-level tool-call bench

19. Run `scripts/bench/bench_api_tool_call.py` against the same endpoint. Save to:
    ```
    docs/models/benchmarks/qwen36-35b-a3b-4bit/api-tool-test-dflash-mlx.json
    ```
20. Compare against `qwen36-35b-a3b-jangtq4-crack/api-tool-test.json` (same base, different server / different uncensoring path).

#### 4c — Agent tool-call bench

21. Run `scripts/bench/bench_agent_tool_call.py` (the agent-bench skill). Save to:
    ```
    docs/models/benchmarks/qwen36-35b-a3b-4bit/agent-bench-dflash-mlx.json
    ```
22. Compare against:
    - `qwen36-27b-6bit/agent-bench-llmster.json` — server-class headline (llmster on a similar-size sibling).
    - `qwen36-35b-a3b-jangtq4-crack/agent-bench.json` — same base, different runtime + quant.

#### 4d — Restore production

23. Stop dflash-mlx: `ssh macstudio "pkill -f dflash-mlx-openai-server"`.
24. Restart Ling-2.6-flash on vllm-mlx using the captured restore command from step 14. Verify with `curl -s http://<MAC_STUDIO_IP>:8000/v1/models`.

### Phase 5 — Documentation (per CLAUDE.md / AGENTS.md Sync Policy)

#### Event 1 — new server type (`dflash-mlx`)

25. Create `docs/servers/dflash-mlx/summary.md` with the standard structure (Overview, Architecture, Installation, Starting the server, Tool use and reasoning, Health check, Performance, Known limitations, See also). Mirror the depth of `docs/servers/llmster/summary.md`. Performance section pulls numbers from Phase 4 JSONs.
26. Add a row to `docs/servers/README.md` runbook index.
27. Update `README.md` — data flow diagram (add `dflash-mlx (sidecar) :8098`), Quick Start launch + stop snippets, Health Check curl + log tail, Servers table row with link to the new summary, maintenance line (`pip install -U dflash-mlx` in `~/dflash-mlx-env/`), Known Limitations entry. Update the "All servers except llmster support JANG…" line to include dflash-mlx in the no-JANG list.
28. Update `docs/current.md` — add dflash-mlx to Sidecars table (or Fallbacks if the bench reveals it's not durable).
29. Update `CLAUDE.md` **and `AGENTS.md`** (mirror): overview paragraph, Architecture bullet, data flow diagram, Common Commands launch + stop, Editing Workflow scope note. Both files identical except line 1-3 header.
30. Update `configs/README.md` — bump `Last updated` date, Server Roles table row, new `clients/dflash-mlx/` config-files section, Switching Servers command block.
31. Create `configs/clients/dflash-mlx/opencode.json` only (provisional posture per the llmster precedent — defer the other four client configs).
32. Update `configs/clients/README.md` — add the `dflash-mlx` row to the Layout table; note "OpenCode template only (provisional)" per the llmster precedent.
33. Skip `scripts/switch_opencode_config.py` SERVERS list update for now — only land it if Phase 4 metrics justify graduating dflash-mlx beyond provisional.

#### Event 3 — new model (`mlx-community/Qwen3.6-35B-A3B-4bit`)

34. **Decision point.** The 6-bit MLX of the same base already has an entry in `docs/models/model-summary.md`. Two options:
    - **(a)** Add a sibling entry for the 4-bit MLX variant near the existing 6-bit entry, noting it's the dflash-mlx target.
    - **(b)** Append the 4-bit context as a "Variants" sub-row inside the existing 6-bit entry.

    **Recommended: (a).** Different on-disk size and different quality envelope than 6-bit; deserves its own row for the README Models table. Add a one-line link from the 4-bit entry to the dflash-mlx server runbook.
35. README.md Models table — add the 4-bit row with "Best For: dflash-mlx speculative decoding (sidecar)" cell.
36. Skip `docs/models/per-model/model-summary-<slug>.md` deep-dive — the model itself is well-documented at the family level, no exotic patches needed (DFlash specifics live in the server runbook).

#### Event 4 — benchmarks

37. The three JSON files from Phase 4 (steps 17, 19, 21) are already at the correct paths.
38. Update `docs/models/benchmarks/model-benchmark-api-server.md` — add a row for `qwen36-35b-a3b-4bit + dflash-mlx`, link the JSON.
39. Update `docs/models/benchmarks/model-benchmark-agent-tool-call.md` — add a row, link the JSON, include the headline speedup vs llmster on Qwen3.6-27B if material.
40. **Decision point — `model-benchmark-tool-call.md`?** No such file exists yet for tool-call API benches. Two options:
    - **(a)** Create `docs/models/benchmarks/model-benchmark-api-tool-call.md` mirroring `model-benchmark-agent-tool-call.md`.
    - **(b)** Roll the API tool-call results into a section of `model-benchmark-agent-tool-call.md`.

    **Recommended: (a)** for searchability and to keep Sync Policy honest. Small file, easy index lookup.
41. README.md Benchmarks section — update the headline tables only if a new fastest/slowest extreme emerges (e.g., dflash-mlx beats llmster's ~26-32 s end-to-end on a comparable model, or fails to).
42. Update `docs/models/model-summary.md` caveats only if Phase 4 reveals a production-impacting finding (faster server, broken tool-call path).

#### Event 5 — script (only if a launch wrapper lands)

43. If steps 9 and 23 motivate adding `scripts/bench/run_dflash_mlx.py` or `scripts/dflash_mlx_launch.sh`, add it to `scripts/README.md` under the appropriate subsection. **Default: don't ship a wrapper** — the one-line nohup invocation in step 9 is fine and lives in CLAUDE.md / AGENTS.md.

#### Pre-commit drift check

44. Before each commit:
    ```bash
    grep -n "dflash\|Qwen3.6-35B-A3B-4bit" README.md AGENTS.md CLAUDE.md configs/README.md docs/current.md docs/models/model-summary.md
    ```
    Confirm references are consistent before pushing.

#### Event 6 — plan lifecycle

45. When Phase 5 commits land: `git mv plans/active/plan-dflash-mlx-deploy.md plans/done/plan-dflash-mlx-deploy.md` and move the row in `plans/README.md` from Active to Done. Add a 2-line "Implementation:" block at the top of the moved plan with commit hashes and the runbook path.

## Outputs

**Server runbook:**
- `docs/servers/dflash-mlx/summary.md` — full runbook
- Row in `docs/servers/README.md`

**Catalog updates:**
- `docs/models/model-summary.md` — new 4-bit MLX entry near the 6-bit sibling (option 34a)
- `README.md` — Models table row, Servers table row, data-flow diagram update, Known Limitations entry
- `docs/current.md` — Sidecars row

**Top-level instruction docs (kept in sync):**
- `CLAUDE.md` and `AGENTS.md` — overview, Architecture, Common Commands, scope note

**Configs:**
- `configs/clients/dflash-mlx/opencode.json` — OpenCode template only (provisional)
- `configs/README.md` — Server Roles, Switching Servers, `Last updated`
- `configs/clients/README.md` — Layout table row

**Benchmarks (Phase 4 outputs):**
- `docs/models/benchmarks/qwen36-35b-a3b-4bit/api-server-dflash-mlx.json`
- `docs/models/benchmarks/qwen36-35b-a3b-4bit/api-tool-test-dflash-mlx.json`
- `docs/models/benchmarks/qwen36-35b-a3b-4bit/agent-bench-dflash-mlx.json`
- `docs/models/benchmarks/model-benchmark-api-server.md` — new row
- `docs/models/benchmarks/model-benchmark-agent-tool-call.md` — new row
- `docs/models/benchmarks/model-benchmark-api-tool-call.md` — **new file** if option 40a is chosen

**Plan lifecycle:**
- `plans/done/plan-dflash-mlx-deploy.md` (after merge)
- `plans/README.md` Active → Done row move

## Risks and decisions

- **Tool-call format unknown.** dflash-mlx is closed-runtime-adjacent (uses MLX kernels but DFlash glue is open). Whether the OpenAI server cleanly emits `tool_calls[]` for Qwen3.6's chat-template format is not documented — Phase 3 smoke step 10 is the gate. If it fails, this becomes a "library-mode only" deployment and the agent-bench numbers are not meaningful.
- **MLX version pin conflict.** dflash-mlx PyPI package was tested against `mlx 0.31.1`; the existing `vllm-mlx-env` and `mlx-openai-server-env` may be on different MLX builds. Mitigation: dedicated `~/dflash-mlx-env/` venv (Phase 1 step 2). Cost: +0.5 GB of disk, fully isolated.
- **Production downtime in Phase 4.** Phase 4 needs vllm-mlx stopped for ~2 hrs for clean RAM. Mitigation: capture restore command before stop (step 14); explicit restart (step 24). Schedule during a maintenance window.
- **Drafter acceptance under tool-call workloads.** Speculative decoding's win comes from high draft-target agreement on common token sequences. Tool-call structured output (JSON arguments, fixed schema tokens) typically has very high acceptance — but `<tool_call>` boundary transitions and reasoning blocks may dip. Phase 4c (agent-bench) is the empirical answer.
- **Closed-source runtime drift.** dflash-mlx version + the MLX runtime extension version pair to the test results. Record both in each bench JSON header.
- **Q2 outcome may be "no, not enough."** If the realised speedup on M3 Ultra is < 2× over `qwen36-35b-a3b-6bit/api-server-mlx-openai-server.json`, that's still a useful answer — DFlash's published gains are concurrency=1 with optimal block sizes; agent loops with long prefills may not see the same lift. Document and move on.

## Open questions for the user before starting

1. OK to consume ~24 GB of disk on macstudio for the target+drafter pair?
2. Is now an acceptable maintenance window for Phase 4 (~2 hrs of Ling-2.6-flash downtime) — or schedule it?
3. **Sync Policy decision — option 34**: add a sibling 4-bit entry next to the existing 6-bit `model-summary.md` row (recommended), or append as a Variants sub-row?
4. **Sync Policy decision — option 40**: create `docs/models/benchmarks/model-benchmark-api-tool-call.md` (recommended) or fold the API tool-call results into the existing agent-tool-call file?
5. Provisional client-config posture (mirrors llmster: `opencode.json` only) — agreed, or backfill the full client config set up front?
6. Default port for dflash-mlx: stick with the upstream default `8098`, or override to a different port? (Not 8000 — production primary needs that.)
