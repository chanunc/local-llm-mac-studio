# Current Live Stack

Short source of truth for the Mac Studio stack's live operating state. Detailed runbooks live under [`docs/servers/`](servers/), model details under [`docs/models/`](models/), and client templates under [`configs/clients/`](../configs/clients/).

Last verified: 2026-05-15 (production switched from `llama-cpp-mtp` + Qwen3.6-27B-MTP UD-Q6_K_XL to `lm-studio` + `mradermacher/Huihui-gemma-4-26B-A4B-it-abliterated-i1-GGUF` `i1-Q6_K` — huihui-ai abliterated Gemma 4 26B-A4B sparse MoE on the standard LM Studio runtime; deploy-and-benchmark of the uncensored Gemma 4 sibling reclaimed the active server slot. The prior llama-cpp-mtp + Qwen3.6-27B-MTP main is stopped on disk and restartable from the Fallbacks table)

## Production

| Field | Value |
|:--|:--|
| Server | `lm-studio` (LM Studio headless, port 1234) |
| Model | `gemma4-26b-a4b-huihui-abliterated-q6k` (`mradermacher/Huihui-gemma-4-26B-A4B-it-abliterated-i1-GGUF:i1-Q6_K` — huihui-ai refusal-direction abliteration on `google/gemma-4-26B-A4B-it` sparse MoE 26B/4B-active, mradermacher imatrix Q6_K GGUF, 22.64 GB on disk / 21.08 GiB resident, Apache 2.0 base) |
| Port | `1234` (LAN-bound `0.0.0.0:1234`, no auth, CORS enabled) |
| Auth | None |
| Client template set | [`configs/clients/lm-studio/opencode.json`](../configs/clients/lm-studio/opencode.json) — OpenCode template (full lm-studio set: OpenCode, OpenClaw, Claude Code, Pi, Qwen-Code). Uncensored entry duplicated into [`docs/models/uncen-model/client-configs/lm-studio/`](models/uncen-model/client-configs/lm-studio/). |
| Runbook | [`docs/servers/lm-studio/summary.md`](servers/lm-studio/summary.md) · family pitfalls [`docs/models/per-model/model-summary-gemma.md`](models/per-model/model-summary-gemma.md) · per-model deploy + bench [`docs/models/uncen-model/gemma4-26b-a4b-huihui-abliterated-benchmark.md`](models/uncen-model/gemma4-26b-a4b-huihui-abliterated-benchmark.md) |

> 🟢 **Browse-speed all-time leader + 9/10 mlabonne — first Gemma 4 entry to clear 9/10.** API harness `bench_api_tool_call.py` passes **5/5** single-call + 3-turn multi-turn **1.93 s** at the OpenAI layer; OpenCode 1.14.50 end-to-end: browse **2.55 s wall** 🥇 (13 % faster than the prior TrevorJS Q8_0 leader 2.93 s), search 19.59 s wall (agent picks `task` subagent for HN-shape prompts vs `webfetch` on the TrevorJS sibling — tool-pick divergence rather than a regression). Refusal: 9/10 complied at temp=1.0, max_tokens=1024 (only P4 detailed-bomb-instructions refused; P7 racism + P8 bomb tutorial both comply with full content). Smallest-resident Gemma 4 26B-A4B uncensored on this stack (21.08 vs 25.02 GiB for the TrevorJS Q8_0 sibling).

Launch shape (Event-2 ps -axo capture from the running process on Mac Studio):

```bash
# Production switch command, captured 2026-05-15 from `ps -axo command=`:
# Pre-flight: stop the prior llama-cpp-mtp main on port 8100 so the unified-memory budget is clean.
ssh macstudio "pkill -f 'llama-cpp-mtp/build/bin/llama-server'; sleep 3"

# One-time: hub download + hardlink import (idempotent; lms get mis-resolves the i1-Q6_K filename).
ssh macstudio "python3 -c \"from huggingface_hub import hf_hub_download; \
  hf_hub_download(repo_id='mradermacher/Huihui-gemma-4-26B-A4B-it-abliterated-i1-GGUF', \
  filename='Huihui-gemma-4-26B-A4B-it-abliterated.i1-Q6_K.gguf', \
  local_dir='/Users/chanunc/.cache/hauhau-gguf')\""
ssh macstudio "~/.lmstudio/bin/lms import -L \
  --user-repo mradermacher/Huihui-gemma-4-26B-A4B-it-abliterated-i1-GGUF -y \
  ~/.cache/hauhau-gguf/Huihui-gemma-4-26B-A4B-it-abliterated.i1-Q6_K.gguf"

# Load with stable identifier + 64K context (guardrail dance: flip off, load, flip back to high).
ssh macstudio "python3 -c \"import json, os; h=os.path.expanduser('~'); p=f'{h}/.lmstudio/settings.json'; \
  s=json.load(open(p)); s['modelLoadingGuardrails']['mode']='off'; json.dump(s, open(p,'w'), indent=2)\"; \
  ~/.lmstudio/bin/lms load 'huihui-gemma-4-26b-a4b-it-abliterated-i1' --gpu max --context-length 65536 \
    --identifier 'gemma4-26b-a4b-huihui-abliterated-q6k' -y; \
  python3 -c \"import json, os; h=os.path.expanduser('~'); p=f'{h}/.lmstudio/settings.json'; \
    s=json.load(open(p)); s['modelLoadingGuardrails']['mode']='high'; json.dump(s, open(p,'w'), indent=2)\""

# Start server (LAN-bound, CORS).
ssh macstudio "~/.lmstudio/bin/lms server start --bind 0.0.0.0 --cors"

# Stop:
ssh macstudio "~/.lmstudio/bin/lms server stop && ~/.lmstudio/bin/lms unload --all"
```

Notes:
- Switched 2026-05-15 from llama-cpp-mtp + unsloth Qwen3.6-27B-MTP UD-Q6_K_XL to lm-studio + mradermacher Huihui-gemma-4-26B-A4B-it-abliterated i1-Q6_K. Deploy-and-benchmark of the uncensored Gemma 4 sibling — Phase 4 hygiene stopped the prior llama-cpp-mtp main; new model becomes the live process. Prior MTP main is the speed-first fallback for MTP-specific experiments, but the new main is **14× faster on the same browse prompt** (2.55 s vs 35.98 s) so the MTP fallback is not the right choice for raw agent-loop speed.
- **API-level performance** (2026-05-15, lm-studio streaming SSE). Decode **91.6 / 83.2 / 80.4 / 72.2 tok/s** @ 512 / 4 096 / 8 192 / 32 768 input tokens. Warm TTFT 0.22 / 0.10 / 0.12 / 0.22 s. Prefill 2 430 / 41 957 / 71 578 / 148 231 tok/s. Smoke (`bench_api_tool_call.py`): 5/5 single-call, multi-turn 1.93 s. 65 K context probe HTTP 400 — Gemma 4 sliding-window boundary, same as the TrevorJS Q8_0 sibling. Raw data: [`docs/models/benchmarks/logs/gemma4-26b-a4b-huihui-abliterated/`](models/benchmarks/logs/gemma4-26b-a4b-huihui-abliterated/).
- **Agent-loop.** OpenCode 1.14.50 (1 warmup + 3 measured each scenario): browse **2.55 s wall / 1.73 s LLM** (range 2.14 – 2.67 s), search **19.59 s wall / 18.81 s LLM** (range 14.31 – 23.26 s), 2 turns each. Tool divergence — browse picks `webfetch`, search picks `task` subagent (the TrevorJS sibling picks `webfetch` for both). Bench-rig `PWD` fix from 2026-05-14 carries cleanly to a Gemma 4 lm-studio backend.
- **Apache 2.0 base** — `huihui-ai/Huihui-gemma-4-26B-A4B-it-abliterated` is the Apache 2.0 sparse-MoE Gemma 4 26B (128 experts, ~4 B active) with huihui-ai's refusal-direction abliteration applied. mradermacher's `i1-GGUF` is the imatrix-quantised distribution; this run uses `i1-Q6_K` (the HF card's recommended tiers are `i1-Q4_K_M` "fast, recommended" and `i1-Q4_K_S` "optimal size/speed/quality" — we picked Q6_K for higher fidelity at +6 GB).
- **Reasoning channel** — non-thinking instruct; no `<think>` blocks, all generation visible `content`. Tool-call + reasoning parsers are dispatched by LM Studio's built-in Gemma 4 handler — no `--tool-call-parser` / `--reasoning-parser` flags exist on this runtime.
- **65 K HTTP 400** — same as the TrevorJS sibling: Gemma 4 sliding-window boundary on llama.cpp. Throughput benchmarks capped at 32 K; the model is deployed at 65 K context for headroom, but within-32 K conversations are the safe envelope.
- **No multimodal in this deployment** — the base model is vision-capable; mradermacher hosts mmproj in the matching [static GGUF repo](https://huggingface.co/mradermacher/Huihui-gemma-4-26B-A4B-it-abliterated-GGUF) and we did not load it. Drop the mmproj file next to the main GGUF in `~/.lmstudio/models/mradermacher/Huihui-gemma-4-26B-A4B-it-abliterated-i1-GGUF/` to re-enable vision.
- **Build maintenance** — stock LM Studio runtime; no custom binary. Re-applies cleanly on every `~/.lmstudio/bin/lms` upgrade. `lms get` mis-resolves the `i1-Q6_K` filename (same trap as HauhauCS `K_P` quants) — direct HuggingFace Hub download + `lms import -L` is the canonical path.
- Log: `ssh macstudio "tail -20 ~/.lmstudio/logs/server.log"`.
- Other servers stopped: port 8000 free, port 8098 / 8099 / 8100 free, port 1337 free. comfyui (port 8188) is orthogonal and stays up. All previously deployed mains (llama-cpp-mtp + Qwen3.6-27B-MTP UD-Q6_K_XL, lm-studio + prithivMLmods Q3.6-27B-GLM-5.1-DA, Zyphra ZAYA1-8B on Osaurus, TrevorJS Gemma 4 31B-it Uncensored, lmstudio-community Gemma 4 26B A4B-it Q8_0, unsloth Qwen3.6-35B-A3B-UD-Q6_K, Granite 4.1 30B Q8_0, Gemma 4 31B-it MLX 6-bit, DavidAU Heretic family, prithivMLmods Aggressive, TrevorJS Gemma 4 26B A4B EGA) stay on disk and are restartable from the Fallbacks table below.

## Active Sidecars (no port-bound daemon)

| Use case | Path | Model | Notes |
|:--|:--|:--|:--|
| Speech-to-text | `~/qwen-asr-env/` (Python API, transformers + MPS) | `Qwen/Qwen3-ASR-1.7B` (bf16, 4.7 GB) | Deployed 2026-05-08. RTF 19.06× on 15 s English clip, 0.79 s avg. No `/v1/audio/transcriptions` endpoint — call `Qwen3ASRModel.transcribe(audio=…)` from a Python script. Doesn't compete with port 8000 / 1234 / 8098 / 8099. Runbook: [`docs/servers/qwen-asr/summary.md`](servers/qwen-asr/summary.md). |
| Image generation (port 8188) | `~/comfyui/` (PyTorch 2.11 + MPS, comfy-cli managed) | `SeeSee21/Z-Anime` AIO BF16 — Distill-4-step + Base (~19 GiB each, S3-DiT 6B, Apache-2.0) | Deployed 2026-05-08. Web UI only at `http://192.168.31.4:8188`; no `/v1/images/generations` shim. Wall time @ 1024² (3 timed runs after 1 warm-up): Distill-4-step **17.75 s** (CFG 1.0), Base 28-step **235.16 s** (CFG 4.0). Doesn't compete with port 8000 / 1234 / 8098 / 8099 / 8100. Launch: `nohup ~/comfyui/.venv/bin/python ~/comfyui/main.py --listen 0.0.0.0 --port 8188 --use-pytorch-cross-attention > /tmp/comfyui.log 2>&1 &`. Runbook: [`docs/servers/comfyui/summary.md`](servers/comfyui/summary.md). |

## Stopped / Documented Fallbacks

Models are off (unloaded or stopped) until you restart them. Each row's launch shape is in its server runbook.

| Use case | Server | Model | Status |
|:--|:--|:--|:--|
| Prior production main (2026-05-15, llama-cpp-mtp + Qwen3.6-27B-MTP UD-Q6_K_XL, custom `am17an/llama.cpp@mtp-clean` PR #22673, dense 27 B + MTP self-drafting heads, 26 GB on disk, Apache 2.0, **agent-loop slower than current Huihui main** — browse 35.98 s vs 2.55 s, search 35.24 s vs 19.59 s) | `llama-cpp-mtp` (port 8100) | `qwen3.6-27b-mtp-ud-q6kxl` from `unsloth/Qwen3.6-27B-MTP-GGUF` | On disk at `~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main/Qwen3.6-27B-UD-Q6_K_XL.gguf`. Stopped 2026-05-15 in this deploy's pre-bench hygiene. **MTP-experiment fallback** — restart only when you need to demonstrate MTP self-drafting (84–89 % draft acceptance) or to A/B benchmark MTP speculative decoding. Reload via `ssh macstudio "GGUF=~/.cache/huggingface/hub/models--unsloth--Qwen3.6-27B-MTP-GGUF/snapshots/main/Qwen3.6-27B-UD-Q6_K_XL.gguf; nohup ~/llama-cpp-mtp/build/bin/llama-server -m \"\$GGUF\" -ngl 99 -fa on -np 1 -c 32768 --spec-type draft-mtp --spec-draft-n-max 2 --host 0.0.0.0 --port 8100 --alias qwen3.6-27b-mtp-ud-q6kxl --jinja --reasoning on > /tmp/llama-cpp-mtp.log 2>&1 &"`. **Port 8100 does not displace the Huihui main on port 1234** — both can coexist for A/B benchmarking. |
| Prior production main (2026-05-14 → 2026-05-15, lm-studio + prithivMLmods Q3.6-27B-GLM-5.1-DA Q4_K_M, dense 27 B Qwen3.6 + ViT + GLM-5.1 reasoning-trace distillation, think-on, Apache 2.0, 15.41 GiB resident, **faster agent loop than the prior MTP main but slower than current Huihui main** — browse 11.62 s vs 2.55 s) | `lm-studio` (port 1234) | `qwen3.6-27b-glm51-da-q4km` from `prithivMLmods/Q3.6-27B-GLM-5.1-DA-GGUF` | On disk and registered in `lms ls` as `q3.6-27b-glm-5.1-da`. **Reasoning + vision fallback** — reload via `lms unload --all && lms load 'q3.6-27b-glm-5.1-da' --gpu max --context-length 65536 --identifier 'qwen3.6-27b-glm51-da-q4km' -y; lms server start --bind 0.0.0.0 --cors` (Q4_K_M @ 15.4 GiB is below LM Studio's strict 25 % guardrail, no dance needed). Use this when you want think-on reasoning, full vision (mmproj), or GLM-5.1 reasoning-trace distillation instead of the current non-thinking abliterated Gemma 4 MoE. **Loading this on port 1234 displaces the Huihui main** (lm-studio runs one model per port). |
| Prior uncen-main (2026-05-03 → 2026-05-15, TrevorJS Gemma 4 26B A4B Uncensored Q8_0, EGA abliteration on Gemma 4 26B sparse MoE, non-thinking, 25.02 GiB, 8/10 mlabonne — browse 2.93 s 🥈 / search 7.35 s 🥇 (still the uncensored search-speed leader)) | `lm-studio` (port 1234) | `gemma4-26b-a4b-trevorjs-uncen-q8` from `TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF` | On disk and registered in `lms ls` as `gemma-4-26b-a4b-it-uncensored`. **Search-speed fallback** — reload via `lms unload --all && lms load 'gemma-4-26b-a4b-it-uncensored' --gpu max --context-length 65536 --identifier gemma4-26b-a4b-trevorjs-uncen-q8 -y` (guardrail dance — 25 GiB > strict 25 % threshold). Use this when search-shape prompts matter more than browse — the TrevorJS sibling picks `webfetch` directly where Huihui picks `task` subagent. |
| Prior production main (2026-05-12 → 2026-05-14, Zyphra ZAYA1-8B JANGTQ4 on Osaurus, top-1 CCA + MoE 8.4B/760M, Apache 2.0, 4.99 GB on disk, **agent-broken** at cask 0.18.13 / engine pin `b9da180`) | `vmlx-swift-lm` (Osaurus) | `zaya1-8b-jangtq4` from `JANGQ-AI/ZAYA1-8B-JANGTQ4` | On disk at `~/.osaurus/models/JANGQ-AI/ZAYA1-8B-JANGTQ4`. Osaurus stopped 2026-05-14 in this skill's pre-bench hygiene. Restart with: `OSU_MODELS_DIR=$HOME/.osaurus/models nohup /opt/homebrew/bin/osaurus serve --port 1337 > /tmp/osaurus.log 2>&1 &`. Same JANGTQ HTTP-path regression as documented for ZAYA1: 7-8 tok/s vs M4-Max-RunBench 57 tok/s — wait for [Osaurus PR #1057](https://github.com/osaurus-ai/osaurus/issues/1057) to ship `cb8b3df` before relying on it. |
| Prior production main (2026-05-10 → 2026-05-12, TrevorJS Gemma 4 31B-it Uncensored Q4_K_M, dense 31B no-think, Apache 2.0, 17.40 GiB resident, harness 6-7/10 / manual 10/10 useful-compliance, browse 6.63 s warm) | `lm-studio` | `gemma4-31b-it-uncensored-trevorjs-q4km` from `TrevorJS/gemma-4-31B-it-uncensored-GGUF` | On disk and registered in `lms ls` as `gemma-4-31b-it-uncensored`. Reload via `lms load 'gemma-4-31b-it-uncensored' --gpu max --context-length 65536 --identifier gemma4-31b-it-uncensored-trevorjs-q4km -y` (guardrail dance optional — 17.4 GiB sits below the 25 % threshold). Use this when you want a faster non-thinking dense Gemma alternative to the current GLM-5.1-DA main — 30 tok/s decode, browse 6.63 s warm. **Note:** loading this displaces the current GLM-5.1-DA main (only one model fits on LM Studio per port-1234 instance unless you raise the parallel-model limit). |
| Prior production main (2026-05-07 → 2026-05-10, lmstudio-community Gemma 4 26B A4B-it Q8_0, sparse MoE 26B / 4B-active no-think, browse 2.94 s 🥈 / search 7.20 s scaffolded) | `lm-studio` | `gemma-4-26b-a4b-q8` from `lmstudio-community/gemma-4-26B-A4B-it-GGUF` | On disk and registered in `lms ls` as `gemma-4-26b-a4b-it`. Reload via `lms load 'gemma-4-26b-a4b-it' --gpu max --context-length 131072 --identifier gemma-4-26b-a4b-q8 -y` (guardrail off first — 25 GiB > strict 25% threshold). Use this when MoE speed matters more than uncensored compliance — 87.6 tok/s gen, lighter agent loops than the dense 31B uncensored. |
| Prior production main (2026-05-07 morning → 2026-05-07 evening, unsloth Qwen3.6-35B-A3B UD-Q6_K, sparse MoE 35B/3B-active think-on, browse 4.92 s / search 12.08 s) | `lm-studio` | `qwen3.6-35b-a3b-ud-q6` from `unsloth/Qwen3.6-35B-A3B-GGUF` | On disk and registered in `lms ls` as `qwen3.6-35b-a3b`. Reload via `lms load 'qwen3.6-35b-a3b' --gpu max --context-length 65536 --identifier qwen3.6-35b-a3b-ud-q6 -y` (guardrail off first). Use this when bare imperative prompts matter — Qwen3.6 fires tools without scaffolding. |
| Prior production main (2026-05-06 → 2026-05-07, IBM Granite 4.1 30B Q8_0, Apache 2.0, dense, browse 6.24 s / search 10.51 s) | `lm-studio` | `granite-4.1-30b-q8` from `unsloth/granite-4.1-30b-GGUF` | On disk and registered in `lms ls` as `granite-4.1-30b`. Reload via `lms load 'granite-4.1-30b' --gpu max --context-length 65536 --identifier granite-4.1-30b-q8 -y` (guardrail off first). Stays as the Apache-2.0 fallback when the production main is unloaded for an experiment. |
| Prior production main (2026-05-06, Gemma 4 31B-it MLX 6-bit on mlx-lm, thinking ON, browse 12.33 s / search 35.55 s) | `mlx-lm` (port 8000) | `lmstudio-community/gemma-4-31B-it-MLX-6bit` | On disk at `~/.lmstudio/models/lmstudio-community/gemma-4-31B-it-MLX-6bit`. Restart via the launch shape preserved in this file's git history (commit `1584c46` had the Cellar libexec `mlx_lm.server` invocation as the active Production block). |
| Prior lm-studio main (Gemma 4 31B-it MLX 6-bit, thinking OFF, browse **5.11 s 🥇** / search **6.37 s 🏆**) | `lm-studio` | `gemma-4-31b-it-mlx` from `lmstudio-community/gemma-4-31B-it-MLX-6bit` | On disk — reload via `lms load 'gemma-4-31b-it-mlx' --gpu max --context-length 65536 -y`; then `lms server start --bind 0.0.0.0 --cors`. Guardrail may block — set `modelLoadingGuardrails.mode = "off"` before load, restore after. Verify context with `lms ps` (first load sometimes ignores `--context-length`). |
| Prior lm-studio main (TrevorJS Gemma 4 26B A4B Uncensored, EGA abliteration, 8/10, browse 2.93 s 🥇) | `lm-studio` | `gemma4-26b-a4b-trevorjs-uncen-q8` from `TrevorJS/gemma-4-26B-A4B-it-uncensored-GGUF` | On disk — reload via `lms load 'gemma-4-26b-a4b-it-uncensored' --gpu max --context-length 65536 --identifier gemma4-26b-a4b-trevorjs-uncen-q8 -y` (guardrail off first) |
| Prior lm-studio main (DavidAU 40B Heretic, thinking + content channel, 9/10) | `lm-studio` | `qwen36-40b-davidau-heretic-q6k` from `DavidAU/Qwen3.6-40B-...IMatrix-MAX-GGUF` | On disk — reload via `lms load 'qwen3.6-40b-deck-opus-neo-code-here-2t-ot' --gpu max --context-length 131072 --identifier qwen36-40b-davidau-heretic-q6k -y` (guardrail off first) |
| Gemma 4 31B Heretic (benchmarked 2026-05-03, 7/10 compliance, Thinking variant) | `lm-studio` | `gemma4-31b-davidau-heretic-q6k` from `DavidAU/gemma-4-31B-it-Mystery-Fine-Tune-HERETIC-UNCENSORED-Thinking-Instruct-GGUF` | On disk — reload via `lms load 'gemma-4-31b-it-mystery-fine-tune-heretic-uncensored-thinking-instruct' --gpu max --context-length 131072 --identifier gemma4-31b-davidau-heretic-q6k -y` |
| Prior lm-studio main (prithivMLmods Aggressive, prior browse leader, 10/10) | `lm-studio` | `qwen3.6-35b-a3b-prithiv-aggressive-q6k` from `mradermacher/Qwen3.6-35B-A3B-Uncensored-Aggressive-GGUF` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-aggressive --identifier qwen3.6-35b-a3b-prithiv-aggressive-q6k --gpu max --context-length 65536 -y` |
| Prior lm-studio main (HauhauCS Aggressive, search leader) | `lm-studio` | `qwen3.6-35b-a3b-uncensored-aggressive-q6kp` from `HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive` | On disk — reload via `lms load qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive --identifier qwen3.6-35b-a3b-uncensored-aggressive-q6kp --gpu max --context-length 131072 -y` |
| Prior production main (JANGTQ4 reference) | `vmlx` | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` | Stopped 2026-05-02 |
| DFlash speculative decoding sidecar | `dflash-mlx` | `mlx-community/Qwen3.6-35B-A3B-4bit` + `z-lab/Qwen3.6-35B-A3B-DFlash` | Stopped 2026-05-02. **Target removed from disk 2026-05-07** — re-download via `huggingface-cli download mlx-community/Qwen3.6-35B-A3B-4bit` before restart. Drafter (`z-lab/Qwen3.6-35B-A3B-DFlash`, 905 MiB) still on disk. |
| Previous Ling primary | `vllm-mlx` | `mlx-community/Ling-2.6-flash-mlx-6bit` | Stopped earlier (2026-05-01) |
| Dense Qwen3.6 fallback | `vllm-mlx` | `JANGQ-AI/Qwen3.6-27B-JANG_4M` | Stopped earlier |

To restart vmlx (port 8000):

```bash
BP=/Applications/vMLX.app/Contents/Resources/bundled-python/python
SNAP=~/.cache/huggingface/hub/models--OsaurusAI--Qwen3.6-35B-A3B-JANGTQ4/snapshots/40c1de58e06a9737427e5d64938e56aa339a6204
nohup $BP/bin/python3 -m vmlx_engine.cli serve "$SNAP" \
  --host 0.0.0.0 --port 8000 \
  --enable-auto-tool-choice --tool-call-parser qwen3 --reasoning-parser qwen3 \
  --continuous-batching \
  > /tmp/vmlx-osaurus-qwen36-jangtq4.log 2>&1 &
```

To restart dflash-mlx (port 8098): see [`docs/servers/dflash-mlx/summary.md`](servers/dflash-mlx/summary.md).

## Other Documented Server Roles (all currently stopped)

| Use case | Server | Model | Notes |
|:--|:--|:--|:--|
| DFlash speculative decoding sidecar (port 8098) | `dflash-mlx` | `mlx-community/Qwen3.6-35B-A3B-4bit` target *(removed from disk 2026-05-07 — re-download required)* + `z-lab/Qwen3.6-35B-A3B-DFlash` drafter | Decode-bound win on math / constrained JSON (1.46–1.61× at 4–8 K), regresses on prose (0.62–0.98×). Loses to lm-studio on prefill-bound agent loops. Three local patches required first. See [`docs/servers/dflash-mlx/summary.md`](servers/dflash-mlx/summary.md). |
| Full multi-model roster | `oMLX` | See [`configs/clients/omlx/`](../configs/clients/omlx/) and `/v1/models` when live | Brew service; restart with `brew services start omlx`. |
| JANGTQ reference | `vmlx` | `OsaurusAI/Qwen3.6-35B-A3B-JANGTQ4` | On disk — see restart command above. MiniMax-M2.7-JANGTQ-CRACK and Qwen3.6-35B-A3B-JANGTQ4-CRACK removed from disk 2026-05-05. |
| mlx-openai-server experiments | `mlx-openai-server` | Check live `/v1/models` when running | YAML-config multi-model server. |
| RotorQuant / TurboQuant / PlanarQuant KV-cache experiments (port 8099) | `llama-cpp-turboquant` | `unsloth/Qwen3.6-35B-A3B-UD-Q6_K.gguf` + KV-cache compression — see runbook | Provisional sidecar, currently stopped. **Two forks installed:** (a) `johndpope/llama-cpp-turboquant` `feature/planarquant-kv-cache` at `~/llama-cpp-turboquant/` — supports `iso3/4`, `turbo2/3/4`, `planar3/4`; iso3 is slow on 32 K cold prefill (>600 s timeout). (b) `TheTom/llama-cpp-turboquant` `feature/turboquant-kv-cache` at `~/llama-cpp-thetom/` — supports `turbo2/3/4` only with auto-asymmetric `q8_0` K dispatch + 4-magnitude LUT for pre-M5 + sparse V dequant. **TheTom turbo3 was the agent-loop speed leader on 2026-05-06: browse 6.47 s / search 15.64 s — 2× / 2.27× faster than Gemma 4 baseline.** See [`docs/servers/llama-cpp-turboquant/summary.md`](servers/llama-cpp-turboquant/summary.md) and [`docs/models/techniques/model-technique-rotorquant.md`](models/techniques/model-technique-rotorquant.md). |

## Before Changing Live State

Follow the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state) in `AGENTS.md` / `CLAUDE.md`. At minimum, a production switch must update this file, `README.md`, [`configs/README.md`](../configs/README.md), the matching [`configs/clients/<server>/`](../configs/clients/) templates, and the relevant model/server docs.
