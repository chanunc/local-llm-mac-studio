# Qwen3.8-27B — per-model notes

Alibaba's Qwen3.8-27B (released 2026-08-14, Apache-2.0) is a dense 27.8B multimodal model that shares the `qwen3_5` architecture family with Qwen3.6 — hybrid Gated-DeltaNet plus gated full attention, with a vision tower. It loaded on the existing runtimes here without patches. This doc records five deployments (4-bit MLX, UD-Q4_K_XL + MTP, two 8-bit Q8_0 GGUFs on lm-studio and on llama.cpp, and the uncensored Defiance Q6_K_P + MTP on llama.cpp) and what they measured; the Qwen3.6 family traps in [`model-summary-qwen-3-6.md`](model-summary-qwen-3-6.md) mostly still apply.

## Overview

- Spec table
- lm-studio MLX 4-bit deployment
- llama.cpp UD-Q4_K_XL + MTP deployment
- lm-studio GGUF Q8_0 deployment
- llama.cpp Q8_0 + MTP deployment (draft-depth and flag matrix)
- llama.cpp Defiance Q6_K_P + MTP deployment (uncensored; embedded MTP vs external FastMTP draft)
- Results (4-bit and 8-bit) and the lm-studio-vs-llama.cpp verdict
- Gotchas and caveats
- Related

## Spec table

| Item | Value |
|:--|:--|
| Base | `Qwen/Qwen3.8-27B` — dense 27.8B, 64 layers (16 × [3 Gated-DeltaNet + 1 gated attention]), hidden 5120 |
| Context | 262,144 native (1M with YaRN); loaded here at 131,072 |
| Modality | Text + image/video (`Qwen3_5ForConditionalGeneration`); vision not exercised by these benches |
| Thinking | On by default; `reasoning_effort` xhigh (default) / medium / low via chat-template kwargs |
| Sampling (card) | Thinking: T 1.0, top_p 0.95, top_k 20, min_p 0. Non-thinking: T 0.7, top_p 0.8, top_k 20, presence 1.5 |
| License | Apache-2.0 |
| MLX build | `lmstudio-community/Qwen3.8-27B-MLX-4bit` — 4-bit g64, 16.08 GB (3 shards) |
| GGUF build | `unsloth/Qwen3.8-27B-GGUF` `UD-Q4_K_XL` — 17.56 GB; MTP heads embedded |
| Q8_0 builds | `unsloth/…` `Q8_0` 29.05 GB (MTP layer `blk.64.nextn.*` embedded, 65 blocks) and `ggml-org/…` `Q8_0` 28.60 GB (no MTP layer, 64 blocks); unsloth/bartowski/lmstudio-community Q8_0 and `UD-Q8_K_XL` all carry the MTP layer (checked from GGUF headers) |
| Uncensored build | `ttindall/Qwen3.8-27B-Defiance-Uncensored-MTP-GGUF` `Q6_K_P` — 25.92 GB; HauhauCS Aggressive weights, MTP layer embedded (65 blocks), plus a modified chat template and an optional 903 MB external FastMTP-32K draft |

## lm-studio MLX 4-bit

```bash
# download straight into LM Studio's tree (hf_hub_download via ~/mlx-vlm-env python)
snapshot_download("lmstudio-community/Qwen3.8-27B-MLX-4bit",
                  local_dir="~/.lmstudio/models/lmstudio-community/Qwen3.8-27B-MLX-4bit")
~/.lmstudio/bin/lms load qwen3.8-27b-mlx --gpu max --context-length 131072 --identifier qwen38-27b-mlx-4bit -y
~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors     # explicit — `status || start` did not start it
```

LM Studio recognised the arch as `qwen3_5` (MLX runtime `mlx-llm-mac-arm64-apple-metal-advsimd@1.13.1`); 16 GB is under the load guardrail so no flip was needed.

## llama.cpp UD-Q4_K_XL + MTP (port 8100)

```bash
GGUF=~/.cache/hauhau-gguf/qwen38-unsloth/Qwen3.8-27B-UD-Q4_K_XL.gguf
nohup ~/llama-cpp-mainline/build/bin/llama-server -m "$GGUF" -ngl 99 -fa on -np 1 -c 131072 \
  --spec-type draft-mtp --spec-draft-n-max 2 --host 0.0.0.0 --port 8100 \
  --alias qwen3.8-27b-mtp-ud-q4kxl --jinja --reasoning on > /tmp/llama-cpp-mtp.log 2>&1 &
```

The existing mainline build (334, `ac4cdde`) loaded this GGUF and created the MTP draft context from the main file. No rebuild and no `-md` were needed; the separate `MTP/mtp-Qwen3.8-27B-Q4_0.gguf` in the repo was downloaded but not used.

## lm-studio GGUF Q8_0

```bash
# ggml-org file: no MTP layer, so lm-studio's llama.cpp runtime 2.14.0 can load it
python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download('ggml-org/Qwen3.8-27B-GGUF','Qwen3.8-27B-Q8_0.gguf',local_dir='/Users/chanunc/.cache/hauhau-gguf/qwen38-ggml-org')"
~/.lmstudio/bin/lms import -L --user-repo ggml-org/Qwen3.8-27B-GGUF -y ~/.cache/hauhau-gguf/qwen38-ggml-org/Qwen3.8-27B-Q8_0.gguf
# 28.6 GB exceeds the load guardrail (mode "high", 4 GiB threshold): flip off, load, restore
~/.lmstudio/bin/lms load qwen3.8-27b --gpu max --context-length 131072 --identifier qwen38-27b-q8_0 -y
```

- **The unsloth Q8_0 does not load in lm-studio.** Runtime `llama.cpp-mac-arm64-apple-metal-advsimd@2.14.0` (the newest it offers; `lms runtime update --all` reports up to date) reads the 65th block as a normal layer and fails with `missing tensor 'blk.64.ssm_conv1d.weight'`. Any GGUF that carries the MTP layer has the same problem; use `ggml-org`'s file.
- `lms load` has no MTP or draft option, so lm-studio always decodes without speculation. Default `PARALLEL` is 4.
- If two models share the key `qwen3.8-27b` (MLX and GGUF prefixes), `lms load` warns and takes the first; load by a unique path or keep only one of them imported.

## llama.cpp Q8_0 + MTP (port 8100)

```bash
GGUF=~/.cache/hauhau-gguf/qwen38-unsloth/Qwen3.8-27B-Q8_0.gguf
nohup ~/llama-cpp-mainline/build/bin/llama-server -m "$GGUF" -ngl 99 -fa on -np 1 -c 131072 \
  --spec-type draft-mtp --spec-draft-n-max 1 --host 0.0.0.0 --port 8100 \
  --alias qwen3.8-27b-q8_0 --jinja --reasoning on > /tmp/llama-cpp-mtp.log 2>&1 &
```

Same build 334 (`ac4cdde`) as the 4-bit run. **`--spec-draft-n-max 1` is the measured best on Q8_0** (31.6 tok/s @ 8K, about 29 on real content, 69 % accepted); `n=2` and `n=3` accept less (55 % / 50 %) and `n=3` is no faster than no MTP. Full matrix with `-ub`, `--spec-draft-p-min`, `ngram-mod` and KV-cache rows: [`model-benchmark-api-server.md`](../benchmarks/model-benchmark-api-server.md#q8_0-gguf-lm-studio-vs-llamacpp-with-and-without-mtp). None of those levers beat `n=1` beyond noise; `-ctk q8_0 -ctv q8_0` is a regression at 32K.

## llama.cpp Defiance Q6_K_P + MTP (port 8100)

Uncensored variant: `ttindall/Qwen3.8-27B-Defiance-Uncensored-MTP-GGUF` `Q6_K_P` (25.92 GB). The weights are HauhauCS's Aggressive build; "Defiance" is `defiance-27b.jinja`, a heavily edited chat template with reasoning-effort modes and an uncensored preamble. Full writeup, refusal data and caveats: [`qwen38-27b-defiance-mtp-benchmark.md`](../uncen-model/qwen38-27b-defiance-mtp-benchmark.md).

```bash
D=~/.cache/hauhau-gguf/qwen38-defiance
nohup ~/llama-cpp-mainline/build/bin/llama-server -m "$D/Qwen3.8-27B-Defiance-Uncensored-Q6_K_P.gguf" \
  -ngl 99 -fa on -np 1 -c 131072 --spec-type draft-mtp --spec-draft-n-max 1 \
  --host 0.0.0.0 --port 8100 --alias qwen38-27b-defiance-q6kp \
  --jinja --chat-template-file "$D/defiance-27b.jinja" \
  --reasoning on --reasoning-format deepseek --reasoning-budget 16384 \
  --temp 0.7 --top-p 0.95 --top-k 64 --min-p 0.05 > /tmp/llama-cpp-mtp.log 2>&1 &
```

The same build 334 (`ac4cdde`) loads the embedded MTP layer; no `-md` needed. `--spec-draft-n-max 1` again beat 2 (27.8 vs 23.6 tok/s @ 512). The repo's headline external draft (`FastMTP-32K`, `-md … --spec-draft-n-max 3`) does not load on build 334 or on upstream master (`output.weight` shape error: the draft has a trimmed 32K vocab). It needs upstream commit `4df29be` plus the HauhauCS patch, built in its own directory.

| Metric | Embedded MTP `n=1` (build 334) | FastMTP-32K `n=3` (patched build) |
|:--|:--|:--|
| API tool smoke | 5/5 · 3-turn loop 11.3 s | 5/5 · 3-turn loop 11.45 s |
| Decode @ 512 → 64K | **27.8 → 18.8 tok/s** | 21.4 → 14.5 tok/s |
| OpenCode browse (wall) | 16.20 s | 16.07 s |
| OpenCode search (wall) | **66.94 s** | 75.29 s |
| MTP draft acceptance | 68 % | 75 % |
| mlabonne refusal (1024 tok) | 9/10 keyword, 10/10 manual | not run |

Raw JSON: [`logs/qwen38-27b-defiance-mtp/`](../benchmarks/logs/qwen38-27b-defiance-mtp/).

## Results

| Metric | lm-studio MLX 4-bit | llama.cpp Q4_K_XL + MTP |
|:--|:--|:--|
| API tool smoke | 5/5 · 3-turn loop 9.06 s | 5/5 · 3-turn loop 12.25 s |
| Decode @ 512 → 64K | 42.2 → 30.1 tok/s | 22.8 → 15.0 tok/s |
| TTFT @ 512 → 64K (cache-warm) | 0.50 → 1.90 s | 0.14 → 0.28 s |
| OpenCode browse (wall / llm) | 18.94 s / 18.1 s | 28.75 s / 27.93 s |
| OpenCode search (wall / llm) | 59.77 s / 58.96 s | 79.61 s / 40.34 s (1/3 hit 300 s) |
| MTP draft acceptance | n/a | 73 % (82/112, one chat probe) |

Full tables: [`model-benchmark-api-server.md`](../benchmarks/model-benchmark-api-server.md), [`model-benchmark-tool-call.md`](../benchmarks/model-benchmark-tool-call.md). Raw JSON: [`logs/qwen38-27b-4bit/`](../benchmarks/logs/qwen38-27b-4bit/), [`logs/qwen38-27b-ud-q4kxl-mtp/`](../benchmarks/logs/qwen38-27b-ud-q4kxl-mtp/).

### 8-bit Q8_0: lm-studio vs llama.cpp

| Metric | lm-studio Q8_0 (ggml-org, no MTP) | llama.cpp Q8_0, no MTP | llama.cpp Q8_0 + MTP `n=1` |
|:--|:--|:--|:--|
| API tool smoke | 5/5 · 3-turn loop 15.45 s | not run | 5/5 · 3-turn loop 10.09 s |
| Decode @ 512 → 32K | 22.7 → 20.3 tok/s (18.0 @ 64K) | 21.8 → 19.5 | **32.0 → 28.2** |
| Real-content decode probe | not run | 21.4 tok/s | **29.3 tok/s** (69 % accepted) |
| Cold prefill (6.5K tok) | 20.9 s (310 tok/s) | 20.9 s (310 tok/s) | 21.3 s (304 tok/s) |
| OpenCode browse (wall / llm) | 33.1 s / 32.08 s | not run | **30.08 s** / 29.23 s |
| OpenCode search (wall / llm) | **42.17 s** / 41.34 s | not run | 48.21 s / 47.42 s |
| Search range over 3 runs | 37.5–88.6 s (one 4-call run) | not run | 43.9–70.1 s |

Raw JSON: [`logs/qwen38-27b-q8-gguf/`](../benchmarks/logs/qwen38-27b-q8-gguf/).

**Verdict on "GGUF on lm-studio is the fastest":** for this model at 8-bit it does not hold. The two servers are tied end to end (sidecar 9 % faster on browse, 14 % slower on search, both inside the run-to-run spread), because cold prefill is identical (about 310 tok/s) and agent turns are prefill-bound. lm-studio's earlier lead on Qwen3.6-27B rows (browse 11–12 s) most likely came from those models (one is a distill with 48–81 reasoning tokens, the others different finetunes) rather than the engine: the same Q8_0 decodes at 22.7 tok/s on lm-studio and 21.8 on llama.cpp without MTP (not proven, since Qwen3.6 was not re-run on both). MTP at depth 1 makes llama.cpp decode about 37 % faster on real content; that shows, if at all, only in OpenCode browse.

Against 4-bit: MLX 4-bit remains the fastest decoder (42.2 tok/s) and the fastest browse (18.94 s), but Q8_0 + MTP `n=1` is the steadier search (48.21 s, 3/3 clean) compared with the Q4_K_XL + MTP `n=2` run (79.61 s median, 1/3 timeout). Single-run samples of 3, so treat as indicative.

## Gotchas and caveats

- **Cold prefill is slow, so agent loops are prefill-bound.** Unique prompts measured about 300 tok/s on lm-studio MLX and about 260 tok/s on llama.cpp. The throughput bench's tens-of-thousands tok/s prefill is cache-warm. OpenCode turns carry 12–24K input tokens, which explains search near 60 s despite 42 tok/s decode.
- **MLX decodes about 1.8× faster than the MTP GGUF** here, but the GGUF has the better warm TTFT.
- **llama.cpp search is unstable.** One of three measured runs ended at the 300 s wall after a six-call `bash` loop. See the [triage note](../benchmarks/logs/qwen38-27b-ud-q4kxl-mtp/agent-tool-call-failure-triage.md).
- **`reasoning_effort: medium` made no measurable difference** on lm-studio (loop 9.0 s vs 9.06 s) — ignored by the MLX path or too short to matter; inconclusive.
- **MTP limits from the llama-cpp-mtp runbook still apply:** `-np 1` only, `--spec-draft-n-max 2`, and no `--mmproj` under MTP, so vision is not available on that sidecar.
- **Python to the LAN is blocked by macOS Local Network Privacy** during these runs; benches went through `ssh -fNL` tunnels to 127.0.0.1.
- **Skill flag trap:** `/deploy-run-benchmark-model --censored no` forces the *uncensored* branch (refusal bench, submodule). Use `--censored yes` for a standard model.
- **FastMTP external draft is slower on M3 Ultra and needs a patched build.** Defiance Q6_K_P: 21.4 vs 27.8 tok/s @ 512 (-23 %), -19 to -23 % at every context to 64K, despite 75 % acceptance. Vendor gains (+11-35 %) were measured on CUDA/Blackwell. Use embedded MTP.
- **Defiance template raises on non-leading system messages** (`System message must be at the beginning.`). OpenCode 1.19.1 did not trigger it; other agents may.
- **Q8_0 + MTP depth matters:** `--spec-draft-n-max 1` beat 2 and 3 on Q8_0; the earlier Q4_K_XL run used 2 and was not re-tested at 1.
- **`--fused-gdn` is not in build 334**, and `-ctk q8_0 -ctv q8_0` costs about 16 % decode at 32K on this model.
- Not run: 256K context probe, vision input, quality evals (8-bit assumed better than 4-bit, not measured), memory footprint, a Q4_K_XL re-run at `n=1`, and an agent bench for the `-ub 2048`, `ngram-mod` and `p-min` rows.

## Related

- Decision-model peers built on Qwen3.8-27B (JEV, pplx-decider) are planned separately in [`plans/active/plan-jev-decision-models.md`](../../../plans/active/plan-jev-decision-models.md).
- Qwen3.6 family: [`model-summary-qwen-3-6.md`](model-summary-qwen-3-6.md).
- llama.cpp MTP runbook: [`docs/servers/llama-cpp-mtp/summary.md`](../../servers/llama-cpp-mtp/summary.md).
- Uncensored Defiance Q6_K_P writeup: [`qwen38-27b-defiance-mtp-benchmark.md`](../uncen-model/qwen38-27b-defiance-mtp-benchmark.md).
