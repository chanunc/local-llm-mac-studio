# Plan v2: Qwen3.8-27B GGUF 8-bit — LM Studio first, llama.cpp sidecar as the comparison

## Context

User's assumption: "running GGUF with LM Studio is the fastest, per `model-benchmark-tool-call.md`." I checked the tables (OpenCode end-to-end and API-level). **Verdict: right for dense think-on Qwen-class models, wrong as a general rule, and never tested for Qwen3.8.** It also shows my v1 plan (a flag matrix on the llama.cpp MTP sidecar) aimed the effort at the arm the repo's own data says is slowest end-to-end for dense 27B. This v2 makes **LM Studio + GGUF Q8_0 the primary arm** and cuts the sidecar to a short comparison. Replaces the v1 plan; saved at `plans/active/plan-qwen38-gguf-q8-fastest.md`.

## Overview

- Verdict and evidence (what the benchmark doc actually says)
- Where the assumption fails
- What changed from v1
- Stage 0 — gates
- Stage 1 — download and import Q8_0
- Stage 2 — Arm A: LM Studio GGUF Q8_0 (primary)
- Stage 3 — Arm B: llama.cpp sidecar, reduced matrix
- Stage 4 — pick the winner; optional runtime updates
- Stage 5 — record results
- Verification and risks

## Verdict and evidence

OpenCode browse / search wall time (`model-benchmark-tool-call.md`, 🧱 Dense), Qwen-class think-on 27B rows:

| Server / format | Model | Browse / search |
|:--|:--|:--|
| **LM Studio GGUF** | HauhauCS Qwen3.6-27B Q8_K_P | **11.16 s** / 28.91 s |
| **LM Studio GGUF** | prithivMLmods Qwen3.6-27B GLM-5.1-DA Q4_K_M | **11.62 s** / 19.47 s |
| LM Studio MLX | Qwen3.8-27B 4-bit | 18.94 s / 59.77 s |
| llama.cpp sidecar + MTP | Jackrong Qwopus3.6-27B Q6_K | 16.96 s / 27.62 s |
| llama.cpp sidecar + MTP | Qwen3.8-27B UD-Q4_K_XL | 28.75 s / 79.61 s (1/3 timeout) |
| LM Studio MLX | Qwen3.6-27B 6-bit | 31.96 s / 25.71 s |
| llama.cpp sidecar + MTP | unsloth Qwen3.6-27B Q6_K_XL | 35.98 s / 35.24 s |
| llama.cpp sidecar + MTP | Heretic v2 Q6_K | 38.99 s / 40.42 s |
| llama.cpp sidecar, LoRA, no MTP | Qwen3.6-27B Fable-5 Q6_K | 40.35 s / 55.59 s |

LM Studio GGUF has the best Qwen 27B browse by about 1.5–3.5x over every sidecar row, even though MTP decodes at similar tok/s. The doc says the same about the Q6_K_XL row: "slower than lm-studio Q4_K_M main".

## Where the assumption fails

1. **It is LM Studio, not GGUF.** MLX on LM Studio is #2 in the dense group (Dolphin Venice 24B 8-bit, 6.62 s) and holds the overall search record (Gemma 4 26B-A4B 4-bit MLX, 3.23 s, 2.2x faster than its own Q8_0 GGUF). For Qwen3.6-35B-A3B the opposite holds: GGUF 4.92 s vs MLX 14.88 s browse on the same server. Format winner depends on the model.
2. **LM Studio is not fastest everywhere.** Hybrid-MoE leader is the llama.cpp MTP sidecar (3.40 s / 12.01 s vs LM Studio Q6_K GGUF 4.92 s / 12.08 s). Where MTP gets 94 tok/s it pays off.
3. **Confounds.** The fastest dense LM Studio rows are no-think (Granite 30B, Gemma 4 31B) or a short-thinking distill (GLM-5.1-DA: 48–81 reasoning tokens in agent context). Only HauhauCS Q8_K_P is plain think-on Qwen.
4. **Qwen3.8-27B was never run as GGUF on LM Studio.** The prediction is an inference from rows 1–2 and may not hold.
5. **Decode and agent speed disagree.** MLX decodes 1.8x faster than the sidecar (42.2 vs 22.8 tok/s) yet is slower end-to-end than LM Studio GGUF on Qwen3.6; the repo attributes the same-GGUF gap on Gemma (LM Studio 2.94 s / 7.20 s vs stock llama.cpp 3.48 s / 9.56 s) to wrapper-layer overhead, not decode.

## What changed from v1

- Primary arm is LM Studio GGUF Q8_0; the 8-row sidecar flag matrix is cut to 3 rows, extended only if the sidecar is competitive.
- Success metric is OpenCode browse/search and cold prefill, not synthetic tok/s.
- Found by read-only checks: `lms load` has **no MTP/draft option**, so LM Studio runs Q8_0 without speculation. The selected llama.cpp runtime is **2.14.0, installed 2026-05-18**, older than the sidecar build 334 (2026-06-10), so it may not load a GGUF that carries the `nextn` layer. Guardrail is `high` with a 4 GiB custom threshold, so a 29 GB load needs the guardrail dance.
- Unchanged: Q8_0 (not UD-Q8_K_XL); all unsloth/bartowski/lmstudio-community Q8_0 files carry the MTP head (`blk.64.nextn.*`, verified from GGUF headers); `ggml-org` Q8_0 does not (64 blocks).

## Stage 0 — Gates (nothing downloads before these)

1. **Ask before stopping** the running `llama-server` on :8100 (27 GB). Event 4 hygiene afterwards; do not restore a prior model.
2. Disk: 50 GiB free (2026-10-18 snapshot, not live state). Q8_0 is 29.0 GB; `29.0 x 1.2 + 5 = 39.8 GB` passes but leaves about 23 GiB. **Ask before downloading** and offer pruning candidates (unused `MTP/mtp-Qwen3.8-27B-Q4_0.gguf` 1.4 GB; the 17.6 GB Q4_K_XL once its numbers are saved). Never auto-delete.
3. Tunnel for benches (Local Network Privacy): `ssh -fN -L 11234:127.0.0.1:1234 -L 18100:127.0.0.1:8100 macstudio` (one tunnel covers both arms). Kill at the end; restore `~/.config/opencode/opencode.json` from a fresh backup.

## Stage 1 — Download and import Q8_0

- `hf_hub_download('unsloth/Qwen3.8-27B-GGUF', 'Qwen3.8-27B-Q8_0.gguf', local_dir='~/.cache/hauhau-gguf/qwen38-unsloth')` over ssh, then `lms import -L --user-repo unsloth/Qwen3.8-27B-GGUF -y <file>` (hard link; no duplicate copy).
- Same file serves both arms, so there is only one 29 GB download.

## Stage 2 — Arm A: LM Studio GGUF Q8_0 (primary)

1. Guardrail dance (CLAUDE.md pattern, one ssh command chained with `;` not `&&` so the restore runs even if the load fails): set `modelLoadingGuardrails.mode` to `off`; `lms load <internal-name> --gpu max --context-length 131072 --identifier qwen38-27b-q8_0 -y`; restore `high`. Then confirm `modelLoadingGuardrails.mode == "high"` in `~/.lmstudio/settings.json`, then `lms server start --bind 0.0.0.0 --cors` (explicit; `status || start` did not start it last time).
2. **Smoke-load first.** If runtime 2.14.0 rejects the file (unknown tensor/arch), the blocker is the runtime: ask before `lms runtime update`, then retry. Last resort is `ggml-org` Q8_0 (28.6 GB, no `nextn`), which needs a prune first.
3. Benches, same as earlier rows: `bench_api_tool_call.py` (pass >= 4/5), `bench_api_server.py --contexts 512,4096,8192,32768,65536 --max-tokens 50 --warmup 1 --runs 2`, then `switch_opencode_config.py` (re-point base URL at the tunnel with sed) and `bench_agent_tool_call.py --scenario both --warmup 1 --runs 3 --skip-permissions`.
4. **Cold-prefill probe** (cache-warm prefill from `bench_api_server.py` overstates agent-loop speed). Same command for both arms; only `PORT` (1234 / 8100) and `MODEL` change. The random prefix defeats the prompt cache; `max_tokens 1` makes total time ≈ prefill time. Run 3 times, report the median seconds and `~8K / seconds` as tok/s:
   ```bash
   ssh macstudio "python3 -c \"import json,uuid; print(json.dumps({'model':'MODEL','max_tokens':1,'messages':[{'role':'user','content':uuid.uuid4().hex+' '+'the quick brown fox '*1600}]}))\" > /tmp/prefill.json && \
     curl -s -o /dev/null -w '%{time_total}\n' -H 'Content-Type: application/json' -d @/tmp/prefill.json 127.0.0.1:PORT/v1/chat/completions"
   ```

## Stage 3 — Arm B: llama.cpp sidecar on the same Q8_0 file (reduced matrix)

**First, clear Arm A** so the two runs never share memory or GPU: `ssh macstudio "~/.lmstudio/bin/lms server stop; ~/.lmstudio/bin/lms unload --all"`, then the Event 4 hygiene check (expect `clean`).

Base: `llama-server -m …/Qwen3.8-27B-Q8_0.gguf -ngl 99 -fa on -np 1 -c 131072 --jinja --reasoning on --host 0.0.0.0 --port 8100 --alias qwen3.8-27b-q8_0`.

| Row | Flags | Question |
|:--|:--|:--|
| B0 | none | true no-MTP baseline (never measured for any Qwen dense 27B here; `model-technique-qwen-3-6-mtp.md:145`) |
| B1 | `--spec-type draft-mtp --spec-draft-n-max 2` | current recipe |
| B2 | `--spec-draft-n-max 1` | shorter drafts (Gemma on this Mac: n=1 best) |
| B3 | `--spec-draft-n-max 3` | deeper drafts (build default; Gemma n=4 regressed) |

Per row: `bench_api_server.py --contexts 512,8192,32768` and one real-content ~300-token decode probe (curl on the Mac, read `timings.predicted_per_second`, `draft_n`, `draft_n_accepted`). Run the OpenCode agent bench on the best row only.

**Extend only if the best sidecar browse is within 25 % of Arm A:** `--spec-draft-p-min 0.5`, `-ub 1024/2048` (prefill), `--fused-gdn on|off` (check `--help` first), `--spec-type draft-mtp,ngram-mod` (untested anywhere; smoke-start first), `-ctk q8_0 -ctv q8_0` at 32K/64K. Otherwise tuning the slower arm is wasted time.

## Stage 4 — Pick the winner; optional runtime updates

- Winner = lowest OpenCode browse and search medians with search not timing out, ties broken by cold prefill. Do not pick by decode tok/s.
- Optional, each needs user approval: `lms runtime update` (Arm A), or an out-of-tree newer llama.cpp build for the sidecar plus the Qwen3.6 MTP regression guard (22.9 tok/s; browse 28–36 s; past rebuild `961e9a3` regressed browse 28 s to 57 s).

## Stage 5 — Record results (Sync Policy; commit only on request)

- Raw JSON to `docs/models/benchmarks/logs/qwen38-27b-q8-gguf/` (one file per arm/row that ran).
- Rows in `model-benchmark-tool-call.md` (dense table, compact `·` Notes, ordered by browse wall) and `model-benchmark-api-server.md` (extend the Qwen3.8 section).
- `docs/models/per-model/model-summary-qwen-3-8.md`: Q8_0 recipes for both arms, the verdict table, and the "never tested" caveat resolved either way.
- `configs/clients/lm-studio/` add `qwen38-27b-q8_0` (must equal the `--identifier` in Stage 2) to `opencode.json`, `pi-models.json`, `openclaw-provider.json`, `qwen-code-settings.json` (insert as text; do not JSON-round-trip, it reformats). `configs/clients/llama-cpp-mtp/opencode.json` only if Arm B runs. `README.md` dense row; `docs/models/model-summary.md` only if Q8_0 earns its own entry.
- No "current/primary" wording; run the CLAUDE.md drift grep. The plan itself lives at `plans/active/plan-qwen38-gguf-q8-fastest.md`; its HTML visual and `plans/README.md` row are still pending (declined earlier for the JEV plan, so ask). Move it to `plans/done/` when finished.
- Ask before committing; commit and push as separate Bash calls.

## Critical files

- `scripts/bench/bench_api_tool_call.py`, `bench_api_server.py`, `bench_agent_tool_call.py`, `scripts/switch_opencode_config.py`
- `docs/models/benchmarks/model-benchmark-tool-call.md` (rows 165–193 are the comparison set), `docs/servers/llama-cpp-mtp/summary.md`, `docs/models/per-model/model-summary-qwen-3-8.md`

## Verification

1. Arm A loads, smoke >= 4/5, throughput table filled, browse/search 3 runs each, cold-prefill number recorded.
2. Arm B rows B0–B3 each have decode, draft acceptance and the real-content probe; B0 makes any MTP gain or loss explicit.
3. The result states, with numbers, whether LM Studio GGUF beats the sidecar for Qwen3.8 Q8_0, and whether it also beats the existing LM Studio MLX 4-bit (18.94 s / 59.77 s) end-to-end.
4. End: `git status` shows only intended docs; tunnels killed; OpenCode config restored; LM Studio guardrail reads `high`; `grep -c qwen38-27b-q8_0 configs/clients/lm-studio/*.json` hits all 4 files and matches `/v1/models` on :1234.

## Risks

- **Runtime age:** LM Studio llama.cpp 2.14.0 (May 2026) may not load Qwen3.8 GGUFs; mitigation is smoke-load first and a gated runtime update.
- **No MTP in LM Studio:** Arm A decodes without speculation, probably in the high teens to low 20s tok/s at Q8_0 (unmeasured). Agent-loop time may still win because the repo's data says prefill and wrapper cost dominate.
- **Disk about 96 % full** after the download; a failed pull needs cleanup.
- **Search `bash` loop** (1/3 on the Q4 sidecar run) may recur on either arm; it is agent-loop behaviour. Run search 3 times and report any timeout.
- **Quality untested:** 8-bit is assumed better than 4-bit, not measured.
- **Cache-warm synthetic benches** overstate prefill; the cold probe and agent bench are the real signals.

## Outcome (executed 2026-10-18)

- Arm A used `ggml-org` Q8_0: lm-studio llama.cpp runtime 2.14.0 (newest offered) cannot load GGUFs with the embedded MTP layer, so the unsloth Q8_0 was sidecar-only.
- Arm A vs best sidecar row (`--spec-draft-n-max 1`): browse 33.1 s vs 30.08 s, search 42.17 s vs 48.21 s. Tied end to end; cold prefill identical (about 310 tok/s).
- Matrix: MTP `n=1` best (+37 % real-content decode); `n=2`/`n=3` worse; `p-min`, `-ub`, `ngram-mod` within noise; KV `q8_0` regresses at 32K; `--fused-gdn` absent in build 334.
- Not done: Stage 4 optional runtime/build updates, quality evals, agent bench for the extension rows.
- Results live in `docs/models/per-model/model-summary-qwen-3-8.md` and the two benchmark docs; this plan can move to `plans/done/` once committed.
