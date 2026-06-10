# Deploy Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-MTP Q6_K

Status: done
Created: 2026-05-20
Completed: 2026-05-20
Canonical: no

## Context

Testing two novel techniques on the Mac Studio MTP sidecar (port 8100):
1. **MTP on MoE** — existing MTP runs dense 27B only; this is 35B/3B MoE, first MoE+MTP in the lab
2. **Claude 4.7 Opus reasoning distillation** — lordx64 LoRA, quality unverified vs base Qwen3.6

The HF page requires **mainline `ggml-org/llama.cpp`**, not the `am17an` MTP fork currently deployed. MTP support has likely merged upstream since the fork was deployed (2026-05-15). Build a new mainline binary in `~/llama-cpp-mainline/` to preserve the existing fork as fallback.

**Quant:** Q6_K (29.2 GB) per user choice for accuracy.

---

## Phase 0: Pre-flight

1. **Disk audit** — `ssh macstudio "df -h ~"` — need ≥35 GB free (29.2 GB model + build artifacts)
2. **Confirm Q6_K filename** — `hf` API list to get exact GGUF filename
3. **Probe mainline MTP support** — shallow clone `ggml-org/llama.cpp`, grep for `draft-mtp` / `mtp` in source. Determines flag name and whether mainline works.
4. **Prompt user** to run `/list-model-to-remove` if disk is tight

**Gate:** disk OK + MTP flag identified. If mainline lacks MTP, fall back to `~/llama-cpp-mtp/` am17an fork.

## Phase 1: Build mainline llama.cpp

New directory `~/llama-cpp-mainline/` (preserves am17an fork at `~/llama-cpp-mtp/`).

```bash
ssh macstudio "cd ~ && git clone --depth 1 https://github.com/ggml-org/llama.cpp.git llama-cpp-mainline && \
  cd llama-cpp-mainline && \
  /opt/homebrew/bin/cmake -B build \
    -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON \
    -DBUILD_SHARED_LIBS=OFF -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_EXAMPLES=ON -DLLAMA_BUILD_SERVER=ON && \
  /opt/homebrew/bin/cmake --build build --config Release -j 8 --target llama-server"
```

~30 sec build. Verify: `~/llama-cpp-mainline/build/bin/llama-server --help | grep -i mtp`

## Phase 2: Download Q6_K GGUF

```bash
ssh macstudio "~/vllm-mlx-env/bin/hf download \
  huihui-ai/Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-MTP-GGUF \
  --include '*Q6_K*.gguf' \
  --local-dir ~/.cache/huggingface/hub/models--huihui-ai--Huihui-Qwen3.6-35B-A3B-Claude-4.7-Opus-abliterated-MTP-GGUF/snapshots/main"
```

Verify file present, ~29.2 GB. Skip any `mmproj-*.gguf` (vision broken with MTP).

## Phase 3: Smoke test

1. Kill any existing MTP process on port 8100
2. Launch with conservative `--spec-draft-n-max 2`:
   ```bash
   ssh macstudio "GGUF=<resolved-path>; nohup ~/llama-cpp-mainline/build/bin/llama-server \
     -m \"\$GGUF\" -ngl 99 -fa on -np 1 -c 32768 \
     --spec-type draft-mtp --spec-draft-n-max 2 \
     --host 0.0.0.0 --port 8100 \
     --alias huihui-qwen36-35b-mtp-abliterated-q6k \
     --jinja --reasoning on > /tmp/llama-cpp-mtp.log 2>&1 &"
   ```
3. Check logs for `MTP draft context` / `speculative decoding context initialized`
4. Health check: `curl /v1/models`
5. Generation smoke: "Count from one to ten" — check coherence + MTP acceptance in `timings`
6. Tool-call smoke: `bench_api_tool_call.py` → target 5/5

**Gate:** model loads, generates, MTP engaged, tool calls parse.

## Phase 4: MTP draft-n-max tuning (2 vs 6)

The HF page recommends `--spec-draft-n-max 6`; existing 27B dense uses 2 (higher dropped acceptance to ~50%). MoE 3B-active may behave differently.

1. Record Phase 3 metrics at n-max 2 (acceptance %, tok/s, TTFT)
2. Restart with `--spec-draft-n-max 6`, repeat same probes
3. **Decision rule:** use 6 if acceptance >70% AND tok/s improves; else stick with 2
4. Document comparison in benchmark notes

## Phase 5: Full benchmarks (pre-bench hygiene)

**Pre-bench hygiene (mandatory):**
```bash
ssh macstudio "pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; \
  pkill -f dflash-serve; pkill -f 'lms server'; \
  /opt/homebrew/bin/brew services stop omlx; sleep 3; \
  ps -axo pid,rss,command | grep -E 'vllm-mlx|mlx-openai-server|vmlx_engine|dflash-serve|lms |omlx' | grep -v grep || echo 'clean'; \
  memory_pressure | head -5"
```

Restart model solo with optimal n-max from Phase 4.

| Benchmark | Script | Output | Notes |
|-----------|--------|--------|-------|
| **Throughput** | `bench_api_server.py` | `logs/huihui-qwen36-35b-mtp-abliterated/perf-llama-cpp-mtp.json` | May need real-content rig if filler-EOS hits (seen on 27B MTP) |
| **Refusal** | mlabonne 10/520 harness | `logs/.../refusal-rate-llama-cpp-mtp.json` | Target 9-10/10 (huihui Gemma 4 scored 9/10) |
| **Agent** | `bench_agent_tool_call.py` | `logs/.../agent-bench-llama-cpp-mtp.json` | Browse + search, 1 warmup + 3 measured |

**Key comparisons:**
- MTP acceptance: MoE 35B/3B vs dense 27B (84-89% baseline)
- tok/s: MoE 3B active should be **much faster** than dense 27B (22.9 baseline)
- Agent browse: vs Gemma 4 huihui 2.55s (leader), TheTom turbo3 6.47s, 27B MTP 35.98s
- Claude distillation: does tool-call quality/reasoning improve vs base Qwen3.6?

## Phase 6: Documentation cascade

**Files to update (single commit):**

| File | Change |
|------|--------|
| `docs/models/per-model/model-summary-qwen-3-6.md` | New variant section (spec table, deploy recipe, perf data) |
| `docs/models/model-summary.md` | Index entry under Qwen3.6 family, update variant count |
| `docs/models/techniques/model-technique-qwen-3-6-mtp.md` | Update "no MoE MTP variant" limitation; add MoE vs dense comparison; update mainline status |
| `docs/servers/llama-cpp-mtp/summary.md` | Add mainline build path, new model to roster, update performance section |
| `docs/models/benchmarks/model-benchmark-tool-call.md` | Summary row in MoE section |
| `docs/models/benchmarks/logs/huihui-qwen36-35b-mtp-abliterated/` | Raw JSON logs directory |
| `configs/clients/llama-cpp-mtp/opencode.json` | Add model to `models` map (keep existing 27B entry) |
| `docs/models/uncen-model/` | Benchmark writeup, update comparison table + test results |
| `README.md` | Models table row if noteworthy results |
| `CLAUDE.md` + `AGENTS.md` | Only if server architecture changes (mainline replaces fork) |

**Sync Policy:** no "current"/"running" assertions anywhere.

## Phase 7: Verify

1. Pre-commit drift check: `grep -rn "current production\|currently running" README.md AGENTS.md CLAUDE.md configs/README.md docs/`
2. Verify cross-refs: `grep -rn "No 35B-A3B MoE MTP variant" docs/` → should be gone
3. Commit (user confirms)

## Risks

| Risk | Mitigation |
|------|-----------|
| Mainline llama.cpp lacks MTP | Fall back to am17an fork binary |
| Both binaries reject MoE+MTP | Model can't be served on this stack; document finding |
| Claude distillation degrades tool-call quality | Phase 3 smoke catches early |
| n-max 6 crashes/garbage | Phase 4 tests safely; revert to 2 |
| Filler-EOS at temp=0 | Real-content prompt rig (established pattern) |

## Critical files

- `docs/servers/llama-cpp-mtp/summary.md` — server runbook
- `docs/models/per-model/model-summary-qwen-3-6.md` — family doc
- `docs/models/techniques/model-technique-qwen-3-6-mtp.md` — MTP technique
- `configs/clients/llama-cpp-mtp/opencode.json` — client config
- `scripts/bench/bench_api_tool_call.py` — tool-call smoke
- `scripts/bench/bench_api_server.py` — throughput bench
- `scripts/bench/bench_agent_tool_call.py` — agent bench
