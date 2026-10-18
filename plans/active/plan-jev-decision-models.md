# Plan: Run JEV decision model (and a similar one) on Mac Studio — separate from Qwen3.8-27B

Status: active
Created: 2026-10-18
Canonical: no

([visual HTML](plan-jev-decision-models.html))

## Context

Run the **JEV decision model and a similar decision model on their own**, split out of the Qwen3.8-27B deploy. The Qwen3.8-27B baseline (LM Studio/MLX, llama.cpp MTP) is **out of scope here** and gets its own plan later. Neither "JEV" nor "Qwen3.8" appeared anywhere in the repo before this plan, so this is a new model class for the lab.

Findings (web + read-only SSH checks, 2026-10-17/18):

- **JEV (AutoTrust)** — "decision model": System 1 = one forward pass → calibrated probabilities for typed `noul` / `choice` / `score` questions (no text generation); System 2 = unmodified Qwen3.8-27B. **Official serving (`serve_decide.py`, `POST /v1/decide`) needs a vLLM dev build + CUDA — not runnable on Mac.** Mac path = community conversion `Bayway/JEV-27B-VL-MLX-4bit` (16.3 GB; LoRA kept unmerged in `jev.safetensors` + float32 decision head; needs fork `Bayway/mlx-vlm@add-jev`; CLI `python -m mlx_vlm decide`, Python `predict()`). Self-reported parity vs reference: KL 0.027, 34/36 top-1; 4-bit can flip near-ties by up to 0.12. JEV GGUF quants skipped (unclear whether adapter is merged; llama.cpp cannot apply the decision head).
- **Similar model: `perplexity-ai/pplx-decider-v1.1-27b`** — also Qwen3.8-27B backbone, `readout.safetensors` head, noncausal full attention. `mlx-community/pplx-decider-v1.1-27b-4bit` (15.3 GB) is self-contained: `decider_mlx.py` + `server.py` (`POST /v1/systemone`, port 8092, unused in repo). Needs Python 3.12+. **Do not** load via `mlx_lm.load` / `mlx_vlm.load`. 8,192-token cap per decision. Vendor claims Decision Index 61.56 vs JEV 57.9 (unverified).
- Other decision families seen but not planned: Mapika `decider` (0.8B–35B-A3B, no MLX builds for 12B/31B), Laya (322M encoder), Kev (train-your-own). Mention-only.
- **Mac Studio** (2026-10-17 snapshot, not live state) — 96 GB RAM; 33 GB free (97 % full); `mlx-vlm-env` is 0.5.0 (leave untouched); system Python 3.9.6, no 3.12, but `/opt/homebrew/bin/uv` exists; no global `hf` CLI; no JEV/pplx weights cached.

## Overview

- Stage 0 — preflight gates (unload prompt, small disk prune, uv 3.12 envs)
- Stage 1 — JEV-27B-VL decision mode (MLX 4-bit, fork venv)
- Stage 2 — pplx-decider-v1.1-27b (MLX 4-bit, :8092 sidecar)
- Stage 3 — small head-to-head decision eval
- Stage 4 — record results per CLAUDE.md Sync Policy (commit only on confirmation)
- Verification and risks

## Stage 0 — Preflight gates (nothing downloads until these pass)

1. `python3 scripts/chk_llm_macstu.py` (read-only). **Ask before unloading** anything loaded in LM Studio, then CLAUDE.md Event 4 hygiene (`lms unload --all`, kill servers, `memory_pressure`).
2. **Disk gate:** two downloads ≈ 32 GB (16.3 + 15.3); after the first only ~17 GB remain, below the skill's `size×1.2 + 5 GB` rule for the second. Run `/list-model-to-remove` (interactive, `--dry-run` first, user picks, hard-link aware). Gate: `df` shows **≥ 45 GB free** before downloading.
3. Isolated envs (never touch `mlx-vlm-env` / `vllm-mlx-env`): `uv venv --python 3.12 ~/jev-mlx-env` and `~/pplx-decider-env`; use each venv's own `hf` for downloads.

## Stage 1 — JEV-27B-VL (MLX 4-bit, decision + System 2)

1. Read the fork diff (community code, single uploader), then `uv pip install -p ~/jev-mlx-env/bin/python "git+https://github.com/Bayway/mlx-vlm@add-jev"`; pin the commit SHA in the runbook.
2. `hf download Bayway/JEV-27B-VL-MLX-4bit`; confirm 3 shards + `jev.safetensors`, `decision_head.json`, `calibration.json`, `PARITY.md`.
3. **Parity smoke** vs model card: SKU AX-330 choice example ≈ `0.2548 / 0.1276 / 0.6169 / 0.0007`; billing example ≈ `0.998`. Command: `python -m mlx_vlm decide --model Bayway/JEV-27B-VL-MLX-4bit --state "…" --questions '{…}'`.
4. Record latency per decision (card: ~1.5 s text, 2.1 s image on M2 Pro) and peak RSS (~17 GB).
5. System 2 (adapter off = plain Qwen3.8-27B 4-bit) via `python -m mlx_vlm generate …` — doubles as the generative baseline for Stage 3 with no extra download.
6. Not attempted: HTTP `/v1/decide` (needs vLLM + CUDA). A ~30-line stdlib wrapper around `predict()` is the cheap fallback only if a client needs HTTP.

## Stage 2 — pplx-decider-v1.1-27b-4bit

1. `hf download mlx-community/pplx-decider-v1.1-27b-4bit --local-dir ~/pplx-decider-4bit`; **read `requirements.txt` first** (tested with mlx-vlm 0.7.6), then `uv pip install -r requirements.txt` into `~/pplx-decider-env`.
2. CLI check: `python decider_mlx.py --model . --state "…" --question '{"type":"noul","instructions":"Is this spam?"}'`.
3. Sidecar: `python server.py --model . --port 8092`; verify bind address. From the MacBook use `ssh -fNL` to 127.0.0.1 (macOS 26 Local Network Privacy blocks python/node → LAN).
4. `sudo pmset -a powermode 2` is recommended by the card but changes system power state — skip unless asked.

## Stage 3 — Head-to-head decision eval (small, sequential)

- New `scripts/bench/bench_decision_models.py` (~60 lines; update `scripts/README.md`): ~12 fixed typed decisions (noul / choice / score; 3 reused from model cards for parity; 3 near-ties; 1–2 image cases for JEV). Per model: top-1 agreement, mean |Δp|, entropy, latency per decision, peak RSS. Extra column: JEV System 2 (non-thinking pick-one prompt) to show what the decision head adds.
- One model resident at a time for latency numbers; `memory_pressure` before each.

## Stage 4 — Record results (CLAUDE.md Sync Policy)

- **Event 3:** new family doc `docs/models/per-model/model-summary-jev-decision.md` (setup, forks, gotchas) + row in `docs/models/README.md`; `docs/models/model-summary.md` index entry; `README.md` Models table.
- **Event 4:** raw JSON → `docs/models/benchmarks/logs/<slug>/`; a decision-model summary table in `docs/models/benchmarks/` (compact `·` Notes) linked from its README.
- **Technique doc** `docs/models/techniques/model-technique-decision-models.md` + techniques `README.md` row. These run as CLI/sidecar, **not** a new server type → no Event 1 cascade and no CLAUDE.md/AGENTS.md edit unless `:8092` should be listed as a server.
- No "current / primary" wording; run CLAUDE.md drift grep. **Ask before committing**; commit and push as separate Bash calls; if push hangs use the `gh` credential helper (osxkeychain stall seen 2026-10-17).

## Critical files

- `scripts/chk_llm_macstu.py`, `scripts/list_model_to_remove.py` (disk prune), `scripts/bench/` (pattern for the new decision bench), `scripts/README.md`
- `docs/models/per-model/model-summary-qwen-3-6.md` and `docs/servers/llama-cpp-mtp/summary.md` (structure templates for the new family doc)
- Remote only: `~/jev-mlx-env`, `~/pplx-decider-env`, `~/pplx-decider-4bit`, HF cache

## Verification

1. Stage 1: JEV parity probabilities within ~0.01 of the card's examples; latency and RSS recorded; System 2 returns coherent text.
2. Stage 2: pplx-decider CLI and `:8092` return probabilities for the same inputs; reachable through the SSH tunnel.
3. Stage 3: comparison table produced; no server left running unrecorded; `git status` shows only intended docs.

## Risks

- **Disk 97 %**: a download before the prune gate can fail mid-way; pruning needs per-item user selection.
- **Community fork / checkpoints** (Bayway fork, mlx-community pplx build) are unreviewed third-party code → isolated venvs, read diff/requirements first, pin SHAs.
- **JEV 4-bit calibration** can shift ≤ 0.12 and flip near-ties; fallback is `nativ-community/JEV-27B-VL-MLX-8bit` (30.7 GB, merged LoRA, different fork `Lazarus-931/mlx-vlm@feat/jev`).
- All quality/benchmark claims (JEV, pplx-decider) are from vendor cards; Stage 3 is the only local evidence.
