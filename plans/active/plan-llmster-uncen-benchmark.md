# Plan: Side-by-side uncensored-model benchmark on llmster (LM Studio)

Status: active
Created: 2026-04-30
Canonical: no

## Context

`llmster` (LM Studio headless on port 1234) was added on 2026-04-30 and showed a 3-5× end-to-end speedup vs. vllm-mlx on standard MLX models in the agent-tool-call bench (`docs/servers/llmster/summary.md:98-100`). Headline prefill number: **47K tok/s @ 32K context**, with TTFT staying flat at ~0.7 s — roughly **150× faster prefill** than vllm-mlx + JANG 4M at the same context length.

**Sync Policy applies.** As of 2026-04-30 (commit `cd5d80f`) `CLAUDE.md` / `AGENTS.md` carry an explicit **Sync Policy** under "Editing Workflow" with per-event checklists. This plan triggers **Event 4 (Running a new benchmark)** for every model in the slate, and **Event 3 (Adding a new model)** for any slate model not already in `docs/models/model-summary.md` — currently *all six*. Phase 4 below has been written against those checklists; do not skip the "minor" docs.

The uncensored-model subtree (`docs/models/uncen-model/`) currently has 10/520-mlabonne compliance results from two test dates:
- 2026-03-27 — Hermes 4 70B and CRACK Qwen3.5-VL-122B 4-bit on vllm-mlx
- 2026-04-20 — MiniMax-M2.7-JANGTQ-CRACK and the two Qwen3.6-35B-JANGTQ CRACK variants on vmlx

llmster's runtime is closed-source and accepts only **MLX safetensors and GGUF** (`docs/servers/llmster/summary.md:140`). That eliminates every JANGTQ winner and every JANG mixed-precision CRACK variant. The remaining roster — purpose-built unfiltered Hermes, weight-surgery-only CRACK MLX, abliteration-only Qwen, and trained-uncensored Dolphin/magnum — has not been benched on llmster yet.

## Goal

Establish whether llmster's prefill advantage carries over to the harmful_behaviors compliance benchmark for the uncensored models that *can* run on it, and produce numbers comparable to the existing vllm-mlx / vmlx results in `docs/models/uncen-model/uncen-model-test-results.md`.

## Questions to answer

1. Does the 3-5× agent-loop speedup translate to compliance-bench wall time on the same model files?
2. Does llmster's MLLM path actually load and serve `dealignai/Qwen3.5-VL-122B-A10B-4bit-MLX-CRACK`, or does the closed-source runtime drop something? (Currently confirmed only on vllm-mlx in MLLM mode.)
3. Is the 9/10 vs 10/10 gap between Hermes-4 (`temp=0.0`) and the JANGTQ leaders (`temp=1.0`) a temperature artifact, or a real ceiling for purpose-built unfiltered models? (Re-run Hermes-4 at `temp=1.0` per the methodology caveat at `uncen-model-test-results.md:17`.)
4. Where does the abliteration-only path (`huihui-ai/Qwen3.5-122B-A10B-abliterated`, GGUF) fall on the compliance/quality curve when given the same hardware budget as the CRACK 122B?

## Non-goals

- Not re-running the JANGTQ CRACK winners on llmster — they require the JANGTQ loader and Metal kernels that ship only inside the MLX Studio DMG's bundled Python (`jjang-ai/jangq#5`). Their 10/10 numbers stand.
- Not benchmarking llmster's GUI features, embeddings, or speculative decoding.
- Not redoing the agent-tool-call bench — that's already covered for `qwen3.6-27b-6bit` in `docs/models/benchmarks/qwen36-27b-6bit/agent-bench-llmster.json`.
- Not adding new client config templates beyond what's already at `configs/clients/llmster/opencode.json`.

## Eligibility filter

Excluded by format constraint:

| Model | Score on prior bench | Reason ineligible |
|---|---|---|
| `dealignai/MiniMax-M2.7-JANGTQ-CRACK` | 10/10 | JANGTQ → vmlx only |
| `dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK` | 10/10 useful | JANGTQ → vmlx only |
| `dealignai/Qwen3.6-35B-A3B-JANGTQ2-CRACK` | 4/10 useful | JANGTQ → vmlx only |
| `dealignai/Qwen3.5-VL-122B-A10B-JANG_4K-CRACK` | — | JANG mixed-precision |
| `dealignai/Qwen3.5-VL-122B-A10B-UNCENSORED-JANG_2S` | — | JANG mixed-precision |
| `dealignai/Nemotron-3-Super-120B-A12B-4bit-MLX-CRACK-Uncensored` | — | "Drops 697 tensors" load failure documented in `uncen-model-comparison.md:97` |

## Benchmark slate (6 models)

Picked for: (a) llmster format compatibility, (b) prior-benchmark anchor on another server for direct A/B, (c) method/size diversity.

| # | Model | Size / Format | Role | Prior baseline |
|---|---|---|---|---|
| 1 | `NousResearch/Hermes-4-70B` (or `lmstudio-community/Hermes-4-70B-MLX-6bit`) | ~40 GB Q4 GGUF / ~52 GB MLX 6-bit | **Anchor** — direct A/B vs. vllm-mlx 9/10 | vllm-mlx 9/10 @ ~10 s, `temp=0.0` |
| 2 | `dealignai/Qwen3.5-VL-122B-A10B-4bit-MLX-CRACK` | 69.6 GB native MLX, VLM | **Anchor + load test** — does llmster MLLM path work? Re-run vs. vllm-mlx 3/10 | vllm-mlx 3/10 @ 6.0 s, `temp=0.0` |
| 3 | `Hermes 4.3 36B` (MLX or GGUF) | ~20 GB Q4 | Hermes-lineage size scaling at sub-70B | None |
| 4 | `cognitivecomputations/Dolphin-Mistral-24B-Venice-Edition` (8-bit MLX) | ~25 GB | **Method diversity** — only "trained unfiltered" candidate | None |
| 5 | `huihui-ai/Qwen3.5-122B-A10B-abliterated` (GGUF) | ~81 GB Q4 GGUF | **Abliteration anchor at 122B** — pairs with #2 (same arch class, different uncensoring method) + tests llmster GGUF path on a large MoE | None |
| 6 | `mlx-community/magnum-v4-72b-4bit` | ~41 GB Q4 MLX | Dense-72B sanity check, non-Hermes lineage | None |

**Skipped even though llmster could run them:**
- `HauhauCS/Qwen3.5-35B-A3B-Uncensored-Aggressive` — mxfp4 quant unverified on llmster's closed-source runtime; smoke-test only if a slot frees up.
- `huihui-ai/Qwen3.5-35B-A3B-abliterated` — overlaps with #5 in method/family at smaller size.
- `Midnight-Miqu-70B-v1.5` — personal-use license + literary specialization makes it noisy on harmful_behaviors.
- `Dolphin 3.0 R1 Mistral 24B` — overlaps with #4.
- `R1-1776` — not really refusal-removal; out of scope.

## Methodology

Match the existing test setup in `docs/models/uncen-model/uncen-model-test-results.md` so numbers slot directly into the existing tables.

**Prompts:** the same 10/520 mlabonne harmful_behaviors sample already used for the prior runs. Source via `uncen-model-prompts.md` (or pin a JSON fixture if one isn't already there) and reuse byte-for-byte to keep the comparison clean.

**Per-model run:**
- `max_tokens: 300`
- `temperature`: `1.0` for all models (this fixes the `temp=0.0` vs `temp=1.0` ambiguity flagged at `uncen-model-test-results.md:17`; document side-by-side `temp=0.0` re-runs only for #1 and #2 if they fall short, since those are the prior-baseline anchors)
- `top_p: 1.0`, no system prompt (matches the prior runs)
- One full pass per model. Refusal-phrase keyword matcher + spot-check the borderline cases (especially #2 since it's the only VLM in the slate).

**Server config:** start llmster fresh per model — `lms unload --all` between runs so we don't measure a hot prefill cache from the previous model. Capture per-prompt latency from streaming SSE timestamps (`scripts/bench_api_server.py` already does this), not a wall-clock wrapper.

**Comparability gates:**
- Re-run #1 (Hermes-4 70B) at both `temp=1.0` and `temp=0.0`. The `temp=0.0` number is the apples-to-apples vllm-mlx anchor; the `temp=1.0` number aligns with how MiniMax was scored.
- Re-run #2 (CRACK 122B 4-bit) at `temp=0.0` to anchor against its existing 3/10. If llmster won't load it, log the failure mode and move on — that's still a useful data point per Q2.

## Implementation steps

Phased so each phase produces something committable on its own.

### Phase 1 — Pre-flight (1-2 hrs)
1. Confirm llmster runtime is healthy on macstudio (`~/.lmstudio/bin/lms --version`, `lms ls`).
2. Free RAM: `pkill -f vllm-mlx; pkill -f mlx-openai-server; pkill -f vmlx_engine; brew services stop omlx`.
3. Smoke-test the slate by listing each model's HuggingFace path against LM Studio's catalog (`lms get <url>`-style URL with `--dry-run` if supported, otherwise just `huggingface_hub` HEAD checks). Don't download yet.
4. Disk-budget check: ~340 GB total across the six models; macstudio internal SSD vs. external storage decision needs explicit confirmation before pulling. **Pause here and check with user before downloading.**

### Phase 2 — Anchor pair (~2-4 hrs of inference + ~1 hr download per model)
5. Download and bench #1 Hermes-4 70B. Two runs: `temp=0.0` (anchor), `temp=1.0` (re-anchor).
6. Download and bench #2 CRACK Qwen3.5-VL-122B 4-bit MLX. One run at `temp=0.0`. **Decision point**: if llmster fails to load it (closed-source runtime drops VL tensors), record the failure and skip the second `temp=1.0` run for this model.

If both anchors succeed, the 3-5× hypothesis is testable with just these two — commit the partial result before continuing.

### Phase 3 — Method-diversity tail (~3-5 hrs)
7. #3 Hermes 4.3 36B
8. #4 Dolphin-Mistral-24B Venice
9. #5 huihui Qwen3.5-122B-A10B-abliterated GGUF
10. #6 magnum-v4-72b 4-bit

For each: download → load with `--context-length 65536` → bench → unload. Don't skip the unload (model IDs collide if you don't, per `docs/servers/llmster/summary.md:142`).

### Phase 4 — Documentation (per CLAUDE.md / AGENTS.md Sync Policy)

**Submodule-internal updates** (`docs/models/uncen-model/`):
11. Append a new section to `docs/models/uncen-model/uncen-model-test-results.md` titled "llmster (LM Studio) results, 2026-04-30+":
    - Updated summary table with server column = "llmster"
    - Per-model detail blocks matching the existing structure (Status / time / tokens / 1-line analysis per prompt)
    - Side-by-side delta table for #1 and #2 against their vllm-mlx anchors (compliance, avg time, tok/s)
12. Update `docs/models/uncen-model/uncen-model-comparison.md` — Server Compatibility Matrix, fill in the LM Studio column for every row in the slate (currently several cells are blank or only hint at "Yes").
13. One-line update to `docs/models/uncen-model/README.md` Key Findings if any of the new numbers move the recommended-defaults conclusion.
14. Commit and push the submodule first, then bump the parent's submodule pointer in a separate commit (the submodule has its own remote — don't conflate the two).

**Event 4 — Benchmark JSONs (parent repo):**
15. Save raw timings to `docs/models/benchmarks/<model-slug>/refusal-rate-llmster.json` per model (one file per slate entry), following the established `<model-slug>/<benchmark-type>-<server>.json` convention from `agent-bench-llmster.json` precedent (`CLAUDE.md` Event 4). Slug examples:
    - `hermes-4-70b-mlx-6bit/refusal-rate-llmster.json`
    - `qwen35-vl-122b-crack-4bit/refusal-rate-llmster.json`
    - `dolphin-mistral-24b-venice/refusal-rate-llmster.json`
    - `huihui-qwen35-122b-abliterated/refusal-rate-llmster.json`
    - `magnum-v4-72b-4bit/refusal-rate-llmster.json`
    - `hermes-43-36b/refusal-rate-llmster.json`
16. **Decision point — cross-model summary file.** "Refusal-rate" / harmful_behaviors compliance is not currently a benchmark type in the parent repo; the only existing equivalent table lives inside the submodule (`uncen-model-test-results.md`). Two options:
    - **(a) Submodule-only** — keep the table inside the submodule and skip a `model-benchmark-refusal-rate.md` parent file. Cleanest, but breaks the Event 4 "update `docs/models/benchmarks/model-benchmark-<type>.md`" requirement.
    - **(b) Create `docs/models/benchmarks/model-benchmark-refusal-rate.md`** — new cross-model summary file in the parent, mirrors the structure of `model-benchmark-tool-call.md`, links into the submodule for prompt-level detail. Compliant with Sync Policy; small duplication cost.

    Recommended: **(b)**, because it keeps the Sync Policy honest and makes refusal-rate searchable from the parent repo's benchmark index. Flag for explicit user confirmation.

**Event 3 — Adding new models to canonical catalog (parent repo):**
17. **Decision point — `model-summary.md` entries.** None of the six slate models are currently in `docs/models/model-summary.md`. Strict Sync Policy reading (Event 3) says "When a new model file lands … and you serve it" → all six earn entries (~50 lines each = ~300 lines). But the spirit is "production-relevant catalog" — these are research models, not production candidates. Two options:
    - **(a) Skip Event 3** — uncen models stay only in the submodule; `model-summary.md` remains a production-track catalog. Document the carve-out in the Sync Policy or the submodule README so future-Claude doesn't redo this analysis.
    - **(b) Add stub entries** — one short index line + a "see `docs/models/uncen-model/uncen-model-comparison.md` for spec details" pointer per model. ~6 stubs × ~15 lines = ~90 lines. Compliant; avoids the full duplication.

    Recommended: **(b)**, because it lets the parent's Models table reference uncensored options without the submodule becoming a hidden silo.
18. **README.md Models table** — Sync Policy Event 3 says one row per model. If 17(b) is chosen, add the same six rows here with a "research only — see uncen-model docs" Best-For cell. If 17(a), skip.
19. **Client configs** — none of the six are in `configs/clients/llmster/opencode.json`'s `models` map. Add them there only if any earns OpenCode use beyond the bench (default: don't, these are research models).

**Event 4 — README + caveats follow-ups:**
20. Update README Benchmarks section's headline tables only if a new fastest/slowest extreme emerges (e.g. if Hermes-4 70B on llmster lands a wall-time under the current vllm-mlx anchor by enough margin to deserve a callout).
21. If the bench reveals a production-impacting finding, update `model-summary.md` caveats and the relevant `model-summary-*.md` detail file. (Unlikely — these models aren't production candidates.)

**CLAUDE.md ↔ AGENTS.md mirror:**
22. If any change touches `CLAUDE.md` (e.g. a new Known Issues bullet about an llmster failure mode discovered during the bench), the same change must land in `AGENTS.md` per the new Sync Policy. Both files are now tracked (commit `cd5d80f`); they're identical except for the agent-name header.

**Pre-commit drift check** (Sync Policy line 153-159):
23. Before each commit in the documentation phase:
    ```bash
    grep -n "<model-slug>" README.md CLAUDE.md AGENTS.md configs/README.md docs/models/model-summary.md
    ```
    Confirm references are consistent before pushing.

### Phase 5 — Cleanup
15. `lms unload --all` and stop the server. Restart the production server (currently `mlx-community/Ling-2.6-flash-mlx-6bit` on vllm-mlx per the updated `CLAUDE.md`).
16. Decide whether to keep the downloaded models in `~/.lmstudio/models/` or purge — they don't dedup against `~/.cache/huggingface/hub/`, so this is real disk pressure.

## Outputs

**Submodule (`docs/models/uncen-model/`):**
- `uncen-model-test-results.md` — extended with llmster results section
- `uncen-model-comparison.md` — Server Compatibility Matrix LM-Studio column filled in
- `README.md` Key Findings — one-line update if a new conclusion emerges

**Parent repo:**
- `docs/models/benchmarks/<model-slug>/refusal-rate-llmster.json` — one per slate entry (six files), per-model directory convention from `agent-bench-llmster.json` precedent
- `docs/models/benchmarks/model-benchmark-refusal-rate.md` (recommended option 16(b)) — new cross-model summary file in the parent, mirrors `model-benchmark-tool-call.md` structure
- `docs/models/model-summary.md` (recommended option 17(b)) — six stub entries linking into the submodule
- `README.md` — six Models-table rows (only if 17(b) is chosen), plus headline-bench updates if applicable
- (optional) `scripts/bench_uncen_llmster.py` only if existing `bench_api_server.py` can't cover harmful_behaviors with a fixture swap; otherwise reuse it

## Risks and decisions

- **Disk budget (~340 GB).** Pulling the full slate at once is the biggest commitment — needs explicit go-ahead before Phase 2. Alternative: serial download → bench → delete to stay under ~80 GB at any one time.
- **CRACK 122B MLLM-on-llmster is a known unknown.** If it fails to load, we lose the cleanest A/B anchor for Q2. Plan B: substitute with the next-largest CRACK MLX variant the LM Studio runtime supports, or accept that Q2 is "no, not at the VLM tier" and move on.
- **Temperature discipline.** The prior bench mixed `temp=0.0` and `temp=1.0`. Locking everything new to `temp=1.0` and re-running anchors at `temp=0.0` is the only way to disambiguate; if we drop that discipline the new numbers are not comparable to the old ones.
- **Production downtime on macstudio.** Phase 1-3 require all other servers stopped (RAM contention with #5 at 81 GB and #2 at 70 GB on a 96 GB box). Confirm this is an acceptable maintenance window before starting — the production primary is currently `Ling-2.6-flash-mlx-6bit` on vllm-mlx using ~80 GB.
- **Closed-source runtime drift.** Numbers from llmster v0.4.12 + MLX runtime 1.6.0 are pinned to those exact versions. A future LM Studio update could change behavior silently — record both versions in the results file.

## Open questions for the user before starting

1. OK to consume up to ~340 GB of disk on macstudio, or run serial-download-and-purge?
2. Is now an acceptable window for production downtime (Ling-2.6-flash on vllm-mlx will be stopped for the duration)?
3. Should #2 (CRACK 122B 4-bit MLX) re-use the `~/.cache/huggingface/hub/` copy if it's already there, or accept the duplicate download into `~/.lmstudio/models/` (LM Studio doesn't symlink — `docs/servers/llmster/summary.md:141`)?
4. Lock all new runs to `temp=1.0` and only re-anchor #1/#2 at `temp=0.0` — agreed?
5. **Sync Policy decision — option 16:** create `docs/models/benchmarks/model-benchmark-refusal-rate.md` in the parent repo (recommended), or keep the table inside the submodule only?
6. **Sync Policy decision — option 17:** add stub entries to `model-summary.md` for the six slate models (recommended), or carve them out as research-only and skip Event 3?
