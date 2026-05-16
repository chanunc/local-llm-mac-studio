Status: active
Created: 2026-05-14
Canonical: no

# Plan — Deploy `unsloth/Qwen3.6-27B-MTP-GGUF` (6-bit `UD-Q6_K_XL`) as a new `llama-cpp-mtp` sidecar

## Context

The technique doc [`docs/models/techniques/model-technique-qwen-3-6-mtp.md`](../../docs/models/techniques/model-technique-qwen-3-6-mtp.md) (commit `ccd7993`, 2026-05-14) establishes that **no server currently installed on the Mac Studio can run Qwen3.6 MTP**:

- LM Studio bundles a stable llama.cpp — PR #22673 is unmerged, and `lms` exposes no CLI surface for `--spec-type mtp`.
- vllm-mlx / mlx-openai-server / oMLX / vmlx / Osaurus are MLX engines; no GGUF, no MLX MTP path today.
- dflash-mlx is a different speculative algorithm (separate drafter, MLX target).
- Both llama-cpp-turboquant forks (`johndpope`, `TheTom`) are based on llama.cpp branches that have **not** merged the MTP PR.

The practical path is a **new dedicated sidecar `llama-cpp-mtp`** built from `am17an/llama.cpp@mtp-clean` (PR #22673), served on a free port alongside the existing sidecar fleet. This plan deploys the 6-bit variant requested — specifically `UD-Q6_K_XL` (26 GB, Unsloth Dynamic 2.0, the bolded recommendation in the technique doc's quant table) — and follows CLAUDE.md Event 1 (new server type) + Event 3 (new model) + Event 4 (benchmark) checklists end-to-end.

**Why UD-Q6_K_XL over plain Q6_K:** both are single-file (no sharding). `UD-Q6_K_XL` uses Unsloth Dynamic 2.0 selective layer upcasting and is the only 6-bit Unsloth recommends; HF card shows ~0.4 % MMLU gain over `UD-Q4_K_XL` for the 8 GB disk cost. Plain `Q6_K` (22.9 GB) is the static-quantized fallback.

## Outcome

A new sidecar process bound to `0.0.0.0:8100` serving `unsloth/Qwen3.6-27B-MTP-GGUF:UD-Q6_K_XL` with MTP speculative decoding enabled and Qwen3 tool/reasoning parsers wired. Repo docs accurately describe the new server, its launch/stop commands, its client wiring, and its measured performance.

## Pre-deploy prerequisites

1. **Read the family doc first** (CLAUDE.md Event 3 precondition): [`docs/models/per-model/model-summary-qwen-3-6.md`](../../docs/models/per-model/model-summary-qwen-3-6.md) — confirm Qwen3.6 parser flags (`--reasoning-parser qwen3`, `--tool-call-parser qwen3_coder`), K_P trap, and the OpenCode `PWD` regression (already fixed in `bench_agent_tool_call.py`).
2. **Disk-space check** on Mac Studio: `df -h ~`. UD-Q6_K_XL is 26 GB; llama.cpp build artifacts ~1.5 GB; need ≥ 30 GB free.
3. **Pause and prompt the user to free disk + RAM by unloading models before the GGUF download.** Run an audit and surface results, then wait for explicit go-ahead (or `/list-model-to-remove`) before downloading. Do not auto-delete or auto-unload.
4. **No port-8000 displacement.** Sidecar lives on 8100 — Event 4 pre-bench hygiene (stop primary servers) is **not** required for the deploy itself, only when running the perf/agent bench.

## Build the sidecar (Mac Studio, one-time)

```bash
ssh macstudio "git clone -b mtp-clean https://github.com/am17an/llama.cpp.git ~/llama-cpp-mtp && \
  cd ~/llama-cpp-mtp && \
  cmake -B build \
    -DGGML_METAL=ON \
    -DGGML_METAL_EMBED_LIBRARY=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_EXAMPLES=ON \
    -DLLAMA_BUILD_SERVER=ON && \
  cmake --build build --config Release -j 8 --target llama-server"
```

Mirrors the cmake flag set used by `llama-cpp-turboquant` (Metal + embedded library, server-only target). The `-DGGML_CUDA=ON` line from the unsloth README does **not** apply — Mac Studio is Metal.

## Download the GGUF — only after the user confirms disk/RAM is freed

```bash
ssh macstudio "~/comfyui-env/bin/hf download unsloth/Qwen3.6-27B-MTP-GGUF \
  --include 'Qwen3.6-27B-UD-Q6_K_XL.gguf' \
  --local-dir ~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main"
```

(Use the `hf` CLI from `~/comfyui-env/`. Skip `mmproj-*.gguf` — vision is broken with MTP active.)

## Launch shape (port 8100)

```bash
ssh macstudio "GGUF=~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main/Qwen3.6-27B-UD-Q6_K_XL.gguf; \
  nohup ~/llama-cpp-mtp/build/bin/llama-server \
    -m \$GGUF \
    -ngl 99 -fa on -np 1 -c 32768 \
    --spec-type mtp --spec-draft-n-max 2 \
    --reasoning-parser qwen3 --tool-call-parser qwen3_coder \
    --host 0.0.0.0 --port 8100 \
    --alias qwen3.6-27b-mtp-ud-q6kxl \
    --jinja \
    > /tmp/llama-cpp-mtp.log 2>&1 &"
```

Key flag rationale:
- `-np 1`: required (multi-pipeline incompatible with MTP per technique doc).
- `-c 32768`: conservative starting context; bump after smoke if memory allows.
- `--spec-draft-n-max 2`: HF card explicitly caps at 2 — higher values drop acceptance to ~50 %.
- `--reasoning-parser qwen3 --tool-call-parser qwen3_coder`: family-doc-mandated Qwen3.6 parsers.
- `--jinja`: matches the turboquant sidecar; needed for the embedded chat template.

**Stop command:** `ssh macstudio "pkill -f 'llama-cpp-mtp/build/bin/llama-server'"`

## Smoke + benchmark

1. **Health check:** `curl -s http://<MAC_STUDIO_IP>:8100/v1/models` (expect `qwen3.6-27b-mtp-ud-q6kxl`).
2. **API smoke:** `scripts/bench/bench_api_tool_call.py --base-url http://<MAC_STUDIO_IP>:8100/v1`.
3. **Perf bench:** `scripts/bench/bench_api_server.py --base-url http://<MAC_STUDIO_IP>:8100/v1 --model qwen3.6-27b-mtp-ud-q6kxl` → raw JSON at `docs/models/benchmarks/logs/qwen36-27b-mtp/perf-llama-cpp-mtp.json`.
4. **Agent bench:** `scripts/bench/bench_agent_tool_call.py --base-url http://<MAC_STUDIO_IP>:8100/v1 --model qwen3.6-27b-mtp-ud-q6kxl` → `docs/models/benchmarks/logs/qwen36-27b-mtp/agent-llama-cpp-mtp.json`.
5. **Pre-bench hygiene** (Event 4): stop port-8000 primary, lm-studio, dflash, comfyui, turboquant before running perf/agent.

Primary perf comparison is **MTP-enabled (UD-Q6_K_XL)** vs **plain Qwen3.6-27B GGUF on stock llama.cpp** to validate the ~1.5–2× speedup claim. Stock-baseline run is queued for a follow-up plan; this plan stops at "MTP deployed and self-benchmarked."

## Doc updates (Event 1 + Event 3 + Event 4)

**New files:**
- `docs/servers/llama-cpp-mtp/summary.md` — full runbook mirroring `docs/servers/llama-cpp-turboquant/summary.md` structure. Cross-link to the MTP technique doc; don't duplicate.
- `configs/clients/llama-cpp-mtp/opencode.json` — mirror `configs/clients/llama-cpp-turboquant/opencode.json` shape. Other client templates deferred (provisional posture, like dflash-mlx).
- `docs/models/benchmarks/logs/qwen36-27b-mtp/{perf,agent}-llama-cpp-mtp.json` — raw bench output.

**Existing files to edit:**
- `README.md` — data-flow diagram, Servers table, Quick Start launch+stop, Health Check curl, Models table row, Known Limitations entry.
- `CLAUDE.md` **and** `AGENTS.md` (mirror) — overview paragraph, Architecture bullet, data-flow diagram, Common Commands launch+stop blocks.
- run-state is probed via `scripts/chk_llm_macstu.py`, not tracked in docs.
- `docs/servers/README.md` — new runbook index row.
- `configs/README.md` — Server Roles table row, new `clients/llama-cpp-mtp/` section, Switching Servers note.
- `configs/clients/README.md` — Layout-table row.
- `scripts/switch_opencode_config.py` — append `"llama-cpp-mtp"` to `SERVERS`.
- `docs/models/model-summary.md` — Index + per-model section for `unsloth/Qwen3.6-27B-MTP-GGUF` (UD-Q6_K_XL). No new `per-model/` file; fold the deploy details into the technique doc's "How it stacks in this repo" table.
- `docs/models/techniques/model-technique-qwen-3-6-mtp.md` — flip the "How it stacks in this repo" table from `N/A — not deployed` to live values, add a Performance section with the benchmark numbers, update `Last updated`.
- `docs/models/benchmarks/model-benchmark-perf.md` + `model-benchmark-agent.md` — add rows to the cross-model summary tables.

## Verification

1. `curl -s http://<MAC_STUDIO_IP>:8100/v1/models | python3 -m json.tool` returns the alias.
2. `curl` a chat-completion with a single tool — `tool_calls[]` populated, not raw XML in `content`.
3. `bench_api_server.py` decode tok/s with MTP should beat published Qwen3.6-27B GGUF baselines; if it's within noise of stock, MTP heads aren't engaging — re-check `--spec-type mtp` is on the actual `argv` (`ps -ax | grep llama-server`).
4. `bench_agent_tool_call.py` returns `agent_turns >= 1` and a non-empty `tool_calls[]` (validates the OpenCode 1.14.50+ `PWD` fix carries to a llama.cpp backend).
5. Pre-commit drift sweep: `grep -n "llama-cpp-mtp\|Qwen3.6-27B-MTP" README.md AGENTS.md CLAUDE.md configs/README.md docs/models/model-summary.md`.

## Out of scope

- Stock-baseline `unsloth/Qwen3.6-27B-GGUF` (no-MTP) comparison run — separate follow-up plan.
- TurboQuant + MTP combined build (neither fork has merged PR #22673; would need a manual cherry-pick).
- Multimodal/`--mmproj` — known-broken with MTP active.
- 35B-A3B MoE MTP variant — does not exist on HF.
- Production-primary promotion (Event 2) — this is a sidecar; live port-8000 model stays unchanged.
