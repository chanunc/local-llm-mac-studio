Status: done
Created: 2026-10-26
Completed: 2026-10-26
Canonical: no

# Plan — Deploy Strata (Qwen3.8-Flash-Next IQ3_S) on the Mac Studio as a `strata` sidecar, with a same-day llama.cpp baseline

## Context

[Strata](https://github.com/Niko1221/Strata) (MIT, v0.2.6 released 2026-10-25, very fast-moving) is a model-specific inference engine with its own Metal backend for **Qwen3.8-Flash-Next**: a 125B MoE with 48 layers × 512 experts and top-10 routing, hybrid GDN/QSA attention, hyper-connections, a 28.8 GB n-gram table read from the SSD, an MTP head and vision. The research earlier in this session found:

- **No lab server can load it today.** The lab's llama.cpp builds (`~/llama-cpp-mainline` @ `ac4cdde`, `~/llama-cpp-fastmtp` @ `4df29be`) lack the `qwen4exp` architecture, and mlx-lm 0.31.3 has only `qwen3_next`. Upstream llama.cpp master does have `qwen4exp`.
- **The Mac Studio meets every hard requirement.** It has an M3 Ultra with a 60-core GPU, macOS 26.3.1, Metal 4 and the Command Line Tools. With 96 GB of RAM, the engine's `resident_cap` is min(96.6 GB working set, 70% × RAM) = 72.2 GB. IQ3_S needs 54.8 + 12.9 GB of overhead = 67.7 GB, so it stays resident with about 4.5 GB to spare.
- **Disk is the one blocker.** `/System/Volumes/Data` has 42 GiB free and is 96% full. IQ3_S is 54.8 + 28.8 = 83.6 GB to download, plus about 6 GB of MTP layer and pack.
- **Strata's own numbers (M5 Max 128 GB, not the M3 Ultra) are about 1.85× llama.cpp's decode and about 1.6× its prefill.** IQ3_S decodes the story prompt at 94.7 tok/s against 51.1, and reads a 4K prompt at about 1,320 tok/s against 791. On the M3 Ultra, prefill is the biggest unknown: Strata's prompt kernels are built for the M5's neural accelerators, and the M3 has none.
- **Known limits.** Strata has never been tested on an M3 Ultra. It handles one request at a time (`--parallel` is not ported to Metal). Context is measured only to 32K on Macs. LAN clients get a 403 from the DNS-rebinding check unless `allowed_hosts` or an API key is set. The default port 8080 collides with mlx-lm ChindaMT.

**Decisions (user, 2026-10-26):** IQ3_S first. Add a same-day llama.cpp baseline from a separate build dir. LAN access through `allowed_hosts` with no API key.

**Outcome:** a provisional `strata` sidecar on **port 8102** serving Qwen3.8-Flash-Next IQ3_S, benchmarked with the lab's three harnesses and compared head to head with llama.cpp master on the same GGUF. It is documented per CLAUDE.md Events 1, 3 and 4. No doc may claim live state.

## Results (2026-10-26)

- **Deployed:** Strata v0.2.6 `strata` sidecar on 8102, ISTA-DASLab IQ3_S resident (engine RSS 57.3 GB), MTP `--spec 2`, `STRATA_ALLOWED_HOSTS` without a key. `chk_llm_macstu.py` shows `Port 8102 — strata`.
- **Smoke:** 5/5 on both engines. Multi-turn 4.83 s (Strata) vs 6.86 s (llama.cpp).
- **Decode:** Strata 74.3 → 66.3 tok/s @ 578 → 60K vs llama.cpp master `d854d98` 40.2 → 35.2. That is **1.74–1.92×**, the same ratio as upstream's M5 Max.
- **Cold prefill:** Strata 741–786 tok/s vs llama.cpp 628–676, only **1.1–1.2×** (upstream: 1.6–1.8× on the M5 Max's GPU neural accelerators).
- **OpenCode:** Strata browse 20.95 s / search 24.94 s vs llama.cpp **9.67 s / 14.84 s**. Strata's Metal prompt cache keeps only the live session. OpenCode's title call evicts the ~11.9K-token system prompt, so every run re-reads it (15.5 s). The `"env_to_user": true` opt-in made no difference.
- **Prior run-state changed:** the Qwen3.8 Defiance llama-server on 8100 was stopped (Event 4), and OpenCode's live config now points at `strata`.
- Detail: [`docs/servers/strata/summary.md`](../../docs/servers/strata/summary.md), [`docs/models/per-model/model-summary-qwen-3-8-flash-next.md`](../../docs/models/per-model/model-summary-qwen-3-8-flash-next.md).

## Overview

- Phase 0: save this plan into the repo (plus its visual HTML)
- Phase 1: read-only preflight, then disk pruning (**pause for the user**)
- Phase 2: build Strata from source at a pinned tag, then `setup.sh` (model download and preparation)
- Phase 3: launch on 8102, smoke test
- Phase 4: Event 4 hygiene, then the Strata benchmarks
- Phase 5: llama.cpp `qwen4exp` baseline on the same GGUF
- Phase 6: doc and config updates (Events 1, 3 and 4)
- Phase 7: commit and push (separate steps, after user confirmation)
- Verification, risks, out of scope

## Phase 0 — Plan into the repo

Per memory, plans live in the repo and need a visual HTML version:
- This file: `plans/done/plan-strata-macstudio-deploy.md` (was `plans/active/` while in progress).
- Visual version: [`plan-strata-macstudio-deploy.html`](plan-strata-macstudio-deploy.html). Cards and a timeline per phase, styled like `plan-switch-top-model-debug-flag.html`.
- An Active row in `plans/README.md`.

## Phase 1 — Preflight (read-only) and disk

1. Confirm the facts again (they drift): `ssh macstudio "sw_vers -productVersion; df -h /System/Volumes/Data | tail -1; lsof -nP -iTCP:8102 -sTCP:LISTEN || echo free"`. Then `git ls-remote --tags https://github.com/Niko1221/Strata.git | tail` and pin the newest tag (v0.2.6 or later). Read its release notes for Mac/Metal changes.
2. **Disk target: ≥ 110 GB free**, about 70 GB more than today. That covers the 83.6 GB download, about 6 GB of MTP and pack, about 3 GB of Strata build and venv, about 1.5 GB of llama.cpp build, and headroom.
3. Run the existing audit: `python3 scripts/list_model_to_remove.py --dry-run --min-size 10`. Then **stop and let the user choose** what to remove: the interactive run of the same script, or `/list-model-to-remove`. Never delete or unload anything automatically (memory: prompt before large download). Largest roots today: `~/.lmstudio/models` 234G, HF hub 109G, `~/.cache/hauhau-gguf` 77G.

## Phase 2 — Build and set up Strata (source route)

Build from source, not `curl install.sh` or the .dmg. This follows the no-curl-pipe preference, the script can be read before it runs, and the Command Line Tools are already present. The non-login ssh `python3` is 3.9.6, so `setup.sh` fetches its own SHA-pinned standalone Python 3.12 into `~/Strata/.python`. That is accepted: it is self-contained and is the Python upstream tests with.

```bash
ssh macstudio "git clone --branch <TAG> --depth 1 https://github.com/Niko1221/Strata.git ~/Strata"
ssh macstudio "cd ~/Strata && ./setup.sh --check"          # Mac check only, changes nothing
ssh macstudio "cd ~/Strata && nohup ./setup.sh --model IQ3_S --context 65536 --port 8102 --host 0.0.0.0 \
  --vision no --no-browser --no-start --yes > /tmp/strata-setup.log 2>&1 &"
```

- What `setup.sh` does: builds `build-metal/strata` (about 7 min) with metal-cpp and ggml, both pinned. It downloads `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF` `IQ3_S/*` (both repos are ungated, and the HF token is present). It extracts the MTP draft layer (about 5 GB of `Qwen/Qwen3.8-Flash-Next`), writes `strata-<model>.json` plus `run-<model>.sh` in `~/Strata/`, and puts the model files in `~/Strata-data/`.
- Watch it with `tail -f /tmp/strata-setup.log`. If a download is interrupted, rerunning `setup.sh` resumes it.
- `--vision no` keeps the first run text-only (the lab benchmarks are text). It can be turned on later with `--setup --vision yes`.
- Do **not** run any other model server while setup repacks: the engine refuses to start beside a repack, which once froze upstream's Mac.

## Phase 3 — Launch on 8102 and smoke

```bash
ssh macstudio "cd ~/Strata && STRATA_ALLOWED_HOSTS=<MAC_STUDIO_IP>,macstudio,<TAILSCALE_HOST> \
  nohup .venv/bin/python serve/server.py --engine strata --config strata-iq3_s.json --port 8102 \
  > /tmp/strata.log 2>&1 &"
ssh macstudio "pkill -f 'serve/server.py --engine strata'"   # stop (SIGTERM; the server stops its engine)
```

- Use the config filename that setup actually wrote. The code names it `strata-{tag.lower()}.json`, so expect `strata-iq3_s.json` (check with `ls ~/Strata/strata-*.json`).
- `--engine strata` is required: `serve/server.py` defaults to `--engine mock` and port 8095.
- Expect a 1.5–3 min load. `/health` answers only once the model is loaded. Check that the log has `planned resident footprint ... cap ...` and **no** "stream" decision (IQ3_S must stay resident).
- Smoke: `curl -s http://<MAC_STUDIO_IP>:8102/health`, then `curl -s http://<MAC_STUDIO_IP>:8102/v1/models` (record the served model id). Then one chat completion with a single tool: `tool_calls[]` must be filled in, with no raw `<tool_call>` XML in `content`.
- If a LAN request returns `403 Host ... is not allowed`, fix `STRATA_ALLOWED_HOSTS`. Do not add a key.

## Phase 4 — Event 4 hygiene, then the Strata benchmarks

1. Stop all servers using the CLAUDE.md Event 4 block. Also run `pkill -f 'llama-cpp-mainline/build/bin/llama-server'`: the Qwen3.8 Defiance llama-server (34.7 GB RSS) was up when the research ran. Also stop ds4, ollama and Osaurus if they are up. Then check `memory_pressure`. Strata must have the memory to itself.
2. Restart Strata (Phase 3). Use slug `qwen38-flash-next-iq3s` and put logs in `docs/models/benchmarks/logs/qwen38-flash-next-iq3s/`:
   - `python3 scripts/bench/bench_api_tool_call.py --base-url http://<MAC_STUDIO_IP>:8102/v1 --model <id> --output .../api-tool-test-strata.json`
   - `python3 scripts/bench/bench_api_server.py --base-url http://<MAC_STUDIO_IP>:8102/v1 --model <id> --contexts 512,4096,8192,32768 --output .../api-server-strata.json`. Context is capped at 32K because the 65536 ctx cannot fit a 65536-token prompt and upstream measured only to 32K. Then a single `--contexts 60000` probe → `api-server-strata-60k.json`, which is new data.
   - `python3 scripts/switch_opencode_config.py --server strata`, then `python3 scripts/bench/bench_agent_tool_call.py --scenario both --output .../agent-bench-strata.json`. Record the first cold prompt time separately: OpenCode's system prompt is read in full on the first request.
3. Capture the MTP accept stats and the decode/prompt lines from `/tmp/strata.log` for the docs.
4. Do not restore the earlier model afterwards (Event 4 rule).

## Phase 5 — llama.cpp `qwen4exp` baseline (same GGUF, no second download)

```bash
ssh macstudio "git clone --depth 1 https://github.com/ggml-org/llama.cpp ~/llama-cpp-qwen4exp && cd ~/llama-cpp-qwen4exp && \
  grep -c qwen4exp src/llama-arch.cpp && export PATH=/opt/homebrew/bin:\$PATH && \
  cmake -B build -DGGML_METAL=ON -DGGML_METAL_EMBED_LIBRARY=ON -DBUILD_SHARED_LIBS=OFF -DLLAMA_BUILD_TESTS=OFF && \
  cmake --build build --config Release -j 8 --target llama-server"
```

- Use a separate dir so the existing 8100 recipes and their pinned builds stay untouched. Homebrew `cmake` must be on PATH (a lesson from the 2026-10-21 build).
- **Stop Strata first.** The two cannot both be resident (about 68 GB plus about 60+ GB).
- Launch on **8100**, the lab's llama.cpp slot, with the ISTA shard 1 path under `~/Strata-data/` (llama.cpp loads shard 2 through the split): `-m <IQ3_S-00001-of-00002.gguf> -ngl 99 -fa on -np 1 -c 65536 --jinja --alias qwen38-flash-next-iq3s-llamacpp --host 0.0.0.0 --port 8100 > /tmp/llama-cpp-qwen4exp.log`.
- Run the same three harnesses with the same flags and save as `*-llama-cpp.json` in the same logs dir.
- If master fails to load the ISTA files (for example a missing quant type), retry at Strata's ggml pin `3cf0325` (2026-09-20, "CUDA: enable sparse fa for qwen4"). If that fails too, record it as a negative result.
- Stop afterwards with `pkill -f 'llama-cpp-qwen4exp/build/bin/llama-server'`. This build is benchmark-only, so it gets no server type and no chk pattern.

## Phase 6 — Docs and configs (Events 1, 3 and 4)

**New files**
- `docs/servers/strata/summary.md`: full runbook, structured like `docs/servers/ds4/summary.md` (Overview, Architecture, Installation, Download, Starting, Tool use and reasoning, Health check, Performance on M3 Ultra, Known limitations, See also). Include the fit math, the `allowed_hosts` gotcha, the 8080 collision, single-slot queueing, the 32K-measured context, the upstream note on M5 Max kernel panics while streaming (avoided because IQ3_S is resident), and the source-build and update path (`git fetch --tags && git checkout <new tag> && ./setup.sh --build`).
- `configs/clients/strata/opencode.json`: modelled on `configs/clients/ds4/opencode.json`, with provider `macstudio-strata`, `baseURL http://<MAC_STUDIO_IP>:8102/v1`, `apiKey "not-needed"`, `tools: true`, `reasoning: true`, context 65536.
- `configs/clients/strata/claude-code-settings.json`: Strata's native Anthropic API (`ANTHROPIC_BASE_URL=http://<MAC_STUDIO_IP>:8102`, without `/v1`) is a real benefit worth a template. Copy the shape of an existing Anthropic-capable server's template.
- `docs/models/per-model/model-summary-qwen-3-8-flash-next.md`: a separate model, not a 27B variant (arch `qwen4exp`, n-gram table, 125B MoE). This follows the ds4 precedent, `model-summary-deepseek-v4.md`.
- The benchmark JSONs from Phases 4 and 5.

**Edits**
- `scripts/chk_llm_macstu.py`: add a `SERVER_PATTERNS` row (pattern taken from the real `ps` argv, for example `serve/server.py --engine strata`, label `strata`, port 8102). Also add `FALLBACK_SERVER_BY_PORT[8102]`, a `SERVER_LOGS["strata"] = "tail -f /tmp/strata.log"` entry, 8102 in `DEFAULT_PORTS`, and `strata` in `SINGLE_MODEL_SERVERS`.
- `scripts/switch_opencode_config.py`: append `"strata"` to `SERVERS`.
- `README.md`: data flow, Quick Start, Health Check, Servers table, Models table row, Known Limitations. Strata runs no JANG/JANGTQ/`bailing_hybrid`, so update the "All servers except lm-studio support JANG…" line. Update the Benchmarks headlines only if a new extreme is set.
- `CLAUDE.md` **and** `AGENTS.md` (mirrored): server bullet, data-flow line, Common Commands (start, stop, log), and an Event 3 family-table row for Flash-Next.
- `configs/README.md` (Server Roles row, `clients/strata/` section, Switching Servers); `configs/clients/README.md` (Layout row); `docs/servers/README.md` (index row); `docs/models/README.md` (per-model row).
- `docs/models/model-summary.md`: Index entry plus a spec-table section.
- `docs/models/benchmarks/model-benchmark-api-server.md` and `model-benchmark-tool-call.md`: Strata and llama.cpp rows, with Notes in compact `·` format (memory).
- `plans/README.md`: move the plan to `done/` when complete.

## Phase 7 — Commit and push

- Ask the user before committing; the memory rule applies when work is unverified end to end.
- Make one commit for the deploy, docs and benchmarks. Push as its own Bash call, never `commit && push`.
- Run the pre-commit drift check from CLAUDE.md first, plus `grep -rn "currently running\|production" docs/servers/strata`.

## Verification

1. `curl -s http://<MAC_STUDIO_IP>:8102/v1/models | python3 -m json.tool` returns the served id. `python3 scripts/chk_llm_macstu.py` shows `strata` on 8102 and its model.
2. The `api-tool-test` harness passes at least 4/5 (target 5/5), with `tool_calls[]` structured and not XML in content.
3. `api-server-strata.json` decode at 512 tokens should land near upstream's resident IQ3_S band (about 95 tok/s with MTP on the M5 Max). If it is close to the no-MTP value (about 75), MTP is not engaged: check the `--mtp` and `--spec 2` args in the config.
4. Strata decode and prefill against `api-server-llama-cpp.json` at the same contexts. This is the headline result and checks the claimed 1.6–1.85×.
5. `agent-bench-strata.json`: `agent_turns ≥ 1` and a non-empty `tool_calls` for browse and search, compared against the README headline table.
6. `memory_pressure` stays normal during the benchmarks, and the log shows a resident run with no swap-out.
7. `python3 scripts/switch_opencode_config.py --list` includes `strata`, and the drift greps are clean.

## Risks and rollback

- **Untested chip and unknown prefill.** If the prompt path fails on the M3 (a compile error or the M1-Max-style `mm_gu3` threadgroup failure), retry with `STRATA_METAL_PROMPT=window` (slow but exact) and report the failure upstream with logs (`strata doctor` style).
- **Memory.** Resident IQ3_S runs only about 4.5 GB under the cap. Never run another model server beside it. If the log shows a stream decision, stop and investigate rather than forcing with `STRATA_METAL_STREAM=0`.
- **Upstream churn.** Two releases came out on 2026-10-25. Pin the tag, record it in the runbook, and upgrade on purpose.
- **Rollback.** Kill the server, then `rm -rf ~/Strata ~/Strata-data ~/llama-cpp-qwen4exp`, but only after asking the user. Nothing else on the Mac changes: no brew, no system Python, no launchd.

## Out of scope

- UD-Q4_K_XL (it streams from the SSD on 96 GB and is a 111 GB download) and Q2_0. Both are possible follow-up plans.
- Vision benchmarks, the 128K/262K context arms, `--parallel` and the DeepSeek V4.1 Metal port (none of them is ported or measured upstream).
- `switch_top_model.py` recipes and any promotion to a default model (Event 2: none).
- Submitting the M3 Ultra numbers to upstream `docs/COMMUNITY_BENCHMARKS.md`. That is optional and the user's decision, after the results exist.
