# Strata Server Summary

## Index
- [Overview](#overview)
- [Architecture](#architecture)
- [Fit on 96 GB](#fit-on-96-gb)
- [Installation](#installation)
- [Starting the server](#starting-the-server)
- [Tool use and reasoning](#tool-use-and-reasoning)
- [Health check](#health-check)
- [Performance](#performance-mac-studio-m3-ultra-96-gb)
- [Known limitations](#known-limitations)
- [Updating](#updating)
- [See also](#see-also)

---

## Overview

[Strata](https://github.com/Niko1221/Strata) (MIT) is a **model-specific inference engine for Qwen3.8-Flash-Next**. It is C++ with CUDA, HIP, SYCL and Metal backends, plus a Python server (`serve/server.py`). It is not a general GGUF runner. On the PC it splits the MoE across VRAM (hot experts), RAM (all experts) and SSD (the n-gram table). On Apple Silicon that split does not apply. The Mac path is its own Metal kernels (`metal/`), with the experts read in place from the mapped GGUF, plus self-drafting with the model's MTP head.

It is the **first path in the lab that runs Qwen3.8-Flash-Next** (GGUF arch `qwen4exp`). The lab's llama.cpp builds `ac4cdde` (`~/llama-cpp-mainline`) and `4df29be` (`~/llama-cpp-fastmtp`) predate `qwen4exp`, and mlx-lm 0.31.3 has only `qwen3_next`. Upstream llama.cpp master has `qwen4exp`; see [Performance](#performance-mac-studio-m3-ultra-96-gb) for the same-GGUF comparison.

**Status: provisional sidecar.** Built from source at tag **v0.2.6** (`4b9e05a`, 2026-10-25). No patches. Bound to port **8102** with OpenAI `/v1`, Anthropic `/v1/messages` and Responses `/v1/responses` APIs. It coexists with the port-8000 servers and the other sidecars, but needs the memory to itself (see [Fit on 96 GB](#fit-on-96-gb)). The Mac engine runs only the Qwen3.8-Flash-Next family: Strata's Qwen3.6-35B-A3B and DeepSeek V4.1-Flash support is CUDA/HIP only.

## Architecture

```
MacBook                       Mac Studio M3 Ultra (<MAC_STUDIO_IP>)
┌────────────────┐            ┌──────────────────────────────────────────────────┐
│ Claude Code    │            │ strata (port 8102, sidecar)                      │
│ OpenCode       │─── LAN ───>│   ~/Strata/serve/server.py --engine strata       │
│ OpenClaw / Pi  │            │     └─ ~/Strata/build-metal/strata (Metal engine)│
│ Codex CLI      │            │   model: ISTA-DASLab Qwen3.8-Flash-Next          │
└────────────────┘            │     GSQ-RCO IQ3_S (54.8 GB + 28.8 GB n-gram)     │
                              │   MTP draft layer (0.89 GB), --spec 2            │
                              │   OpenAI + Anthropic + Responses APIs            │
                              └──────────────────────────────────────────────────┘
```

- **Model.** Qwen3.8-Flash-Next is a 125B MoE with 48 layers × 512 experts (24,576), 10 routed per token. It uses Gated DeltaNet linear attention plus QSA attention, hyper-connections and a per-token n-gram lookup table. The table is shard 2 of the GGUF (28.8 GB, IQ4_NL), and Strata reads a few rows of it per token from the SSD.
- **Files.** Setup keeps three things in `~/Strata-data/`:
  - `models/IQ3_S/` holds both GGUF shards.
  - `packs/iq3_s` is the pack, a few files that index the experts and hold the tokenizer.
  - `mtp/` holds the MTP draft layer (`mtp-q2_0.gguf` and `rt`), extracted from the original `Qwen/Qwen3.8-Flash-Next` checkpoint.
- **Processes.** `server.py` is the HTTP front end; it parses Qwen XML tool calls into OpenAI `tool_calls`. It starts `build-metal/strata --serve ...` as its child engine, with arguments taken from `~/Strata/strata-iq3_s.json`.

## Fit on 96 GB

The engine keeps a pack resident only while `weights + ~12.9 GB overhead ≤ resident_cap`. On a Mac of 64 GB or more, `resident_cap` = min(`recommendedMaxWorkingSetSize`, 70% × RAM) (`metal/src/engine/arena_budget.h`).

On this Mac Studio: min(96.6 GB, 72.2 GB) = **72.2 GB**. The raised `iogpu.wired_limit_mb=92160` lifts the working set but not the 70% rule.

| Pack | Weights mapped | + overhead | On 96 GB | Download |
|:--|--:|--:|:--|--:|
| Q2_0 | 37.6 GB | 50.5 GB | resident | 66.4 GB |
| IQ3_XXS | 47.0 GB | 59.9 GB | resident | 75.8 GB |
| **IQ3_S** (deployed) | 54.8 GB | 67.7 GB | resident, ~4.5 GB spare | 83.6 GB |
| UD-Q4_K_XL (Unsloth) | 82.6 GB | 95.5 GB | experts stream from the SSD | 111 GB |

Measured with IQ3_S: engine RSS **57.3 GB** after load, and the log line `wrapped (54.8 GB), 65664 cells ... ready in 17011 ms` (the whole file mapped as one Metal buffer; no arena, no streaming). Setup writes `STRATA_METAL_STREAM=0` into the config env for a pack that fits.

Upstream logged three watchdog kernel panics on a 128 GB M5 Max. All of them happened in **streaming** mode under memory pressure, and newer footprint caps plus mlock fixed them. A resident pack is clean file pages that macOS can drop, so IQ3_S does not take that path. **Do not run another model server beside it.**

## Installation

One-time on the Mac Studio. Needs the Command Line Tools (present) and about 90 GB of free disk for IQ3_S.

```bash
ssh macstudio "git clone --branch v0.2.6 --depth 1 https://github.com/Niko1221/Strata.git ~/Strata"
ssh macstudio "cd ~/Strata && ./setup.sh --check"     # Mac check only
ssh macstudio "cd ~/Strata && nohup ./setup.sh --model IQ3_S --context 65536 --port 8102 --host 0.0.0.0 \
  --vision no --no-browser --no-start --yes > /tmp/strata-setup.log 2>&1 &"
```

What setup does:

1. **Python.** The non-login ssh `python3` is 3.9.6, so it downloads a SHA-pinned standalone Python 3.12 into `~/Strata/.python`, then makes `~/Strata/.venv`.
2. **Engine build.** It builds `build-metal/strata` with metal-cpp and llama.cpp's ggml at the pinned `3cf0325`. CMake and Ninja come from pip into the venv. On the M3 Ultra the build took about 20 s.
3. **Model download.** `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF` `IQ3_S/*` (ungated, Apache-2.0): 83.6 GB in about 13 min (≈ 108 MB/s). A rerun resumes an interrupted download.
4. **MTP layer.** It extracts the MTP draft layer from `Qwen/Qwen3.8-Flash-Next` (about 2 min).
5. **Config.** It writes `strata-iq3_s.json` and `run-iq3_s.sh` in `~/Strata/`.

The whole run took 15.5 minutes on 2026-10-26 (06:51:37 → 07:07:03).

No Homebrew formula exists. The source route was chosen over `curl install.sh` and the `.dmg` so the code can be read first, and nothing outside `~/Strata` and `~/Strata-data` changes.

## Starting the server

```bash
ssh macstudio "cd ~/Strata && STRATA_ALLOWED_HOSTS=<MAC_STUDIO_IP>,macstudio,<MAC_STUDIO_LOCAL_HOSTNAME>,<TAILSCALE_IP>,<TAILSCALE_HOST> \
  nohup .venv/bin/python serve/server.py --engine strata --config strata-iq3_s.json --port 8102 \
  > /tmp/strata.log 2>&1 &"
ssh macstudio "pkill -f 'serve/server.py --engine strata'"   # stop (SIGTERM; the server stops its engine)
```

- **`--engine strata`** is required: `serve/server.py` defaults to `--engine mock` on port 8095.
- **`STRATA_ALLOWED_HOSTS`**: without an API key, Strata answers only to `127.0.0.1` and `localhost`. Any other `Host` header gets `403 Host '...' is not allowed (DNS rebinding protection)`. List every name clients use, such as the LAN IP, the `.local` name and the Tailscale IP/name; the port is ignored. The alternative is `--api-key` / `"api_key"` in the config, which turns the check off but makes every client send the key (`chk_llm_macstu.py` sends only the oMLX key). Strata prints `WARNING: no API key` at start; that is expected on this LAN-only setup.
- **Port**: setup's default is 8080, which collides with mlx-lm ChindaMT. `--port 8102` is in both the config and the command line.
- **Load time**: about 30 s to `/health` 200 with the file cache warm. The first request after a start pays about 10 s of first-use cost.
- Logs: `/tmp/strata.log` (server) and `~/Strata/strata-iq3_s.log` (engine: per-request `prompt N tokens = R reused + M read in ... ms`, decode rate, `drafts accepted A of B`).

## Tool use and reasoning

- **Tool calls**: Qwen XML (`<tool_call><function=...>`) is parsed server-side into OpenAI `tool_calls[]`. No parser flag is needed. The Anthropic endpoint returns `tool_use` blocks.
- **Reasoning**: it goes into `reasoning_content`, separate from `content`. Effort is off / low / medium / high through the request's `reasoning_effort`. Off is fastest.
- **One request at a time**: `--parallel` is not ported to Metal, so requests queue FIFO. OpenCode's `small_model` title call waits behind the main call.

## Health check

```bash
curl -s http://<MAC_STUDIO_IP>:8102/health
curl -s http://<MAC_STUDIO_IP>:8102/v1/models | python3 -m json.tool   # id "qwen3.8-flash-next-iq3_s", n_ctx 65536
```

Smoke a tool call:

```bash
curl -s http://<MAC_STUDIO_IP>:8102/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model": "qwen3.8-flash-next-iq3_s",
  "messages": [{"role":"user","content":"Run uptime to check system status"}],
  "tools": [{"type":"function","function":{"name":"run_command","parameters":{"type":"object","properties":{"cmd":{"type":"string"}},"required":["cmd"]}}}],
  "max_tokens": 512, "temperature": 0}' | python3 -m json.tool
```

Expect `finish_reason: "tool_calls"` with `run_command {"cmd":"uptime"}` and an empty `content`.

## Performance (Mac Studio M3 Ultra, 96 GB)

Tested 2026-10-26 on ISTA-DASLab GSQ-RCO **IQ3_S**, Strata v0.2.6, `--spec 2` + MTP, context 65536, vision off. Pre-bench hygiene was done: all other LLM servers stopped, 97% memory free at launch.

### Decode + prefill (`bench_api_server.py`, 50-token gen)

The timed runs of `bench_api_server.py` hit Strata's prompt cache (TTFT 0.06–0.08 s at every size), so its `prefill_tps` column is not prompt reading. Cold prefill below comes from the engine log for the untimed probe request (`0 reused + N read in ... ms`).

| Context (input tokens) | Decode tok/s (MTP) | Cold prefill tok/s | Cold TTFT |
|:--:|:--:|:--:|:--:|
| 578 | **74.3** (73.5–74.3) | 304 | 1.9 s |
| 4,163 | 70.0 | 741 | 5.6 s |
| 8,258 | 67.5 | 785 | 10.5 s |
| 32,834 | 70.9 | 786 | 41.7 s |
| 60,068 | 66.3 | 755 (27.3K new on a 32K cached prefix) | 36.2 s |

- **MTP is engaged**: drafts accepted 22 of 27–30 on the filler prompts, 31–47 of 32–51 on the tool prompts (≈ 78–95%).
- **Decode stays flat from 512 to 60K**, because Gated DeltaNet attention costs O(1) per token.
- **Against upstream's M5 Max 128 GB numbers** (resident IQ3_S, `--spec 2`, MTP): decode is 94–102 tok/s there and 66–78 here; cold prefill is about 1,140–1,320 tok/s there and 741–786 here. The M3 has no GPU neural accelerators, so Strata's Metal 4 `matmul2d` prompt kernels run on the plain simdgroup matrix units. Prefill lands at about 0.6× the M5 Max.

### Smoke (`bench_api_tool_call.py`)

**5/5 single-call pass** (`read_file`, `run_command`, `search_web`+`read_file`, `list_directory`, `run_command`), 1.49–2.71 s per call, every one `finish_reason=tool_calls`. Multi-turn loop: 3 turns in 4.83 s (`read_file → write_file → run_command`).

### OpenCode end-to-end (`bench_agent_tool_call.py`)

1 warmup + 3 measured, `/tmp/agent-bench`.

| Scenario | Wall median | LLM median | Turns | Tools |
|:--|:--:|:--:|:--:|:--|
| Browse www.example.com | **20.95 s** (20.91–20.97 p5–p95) | 20.30 s | 2 | `webfetch` |
| Browse Hackernews latest topic | **24.94 s** (24.92–24.97) | 24.24 s | 2 | `webfetch` |

Zero errors, and `webfetch` fired on every run. **Turn 1 is about 19 s of each run**: OpenCode's ~11.9K-token system prompt is read from scratch every time (`0 reused + 11878 read in 15482 ms`). OpenCode's short title request (`small_model`) runs first, and the Mac engine (v0.2.6) keeps only the live session's prefix. A direct API test showed the same: system prompt A, then an unrelated request, then A again, re-read A in full (`0 reused`). The `"env_to_user": true` config opt-in, which upstream documents for opencode, changed nothing (browse 20.99 s, search 24.75 s, still `0 reused`). That run is kept as `agent-bench-strata-env2user.json`.

### Same GGUF on llama.cpp master (`qwen4exp`)

This is llama.cpp master `d854d98` (2026-10-26), built as the benchmark-only `~/llama-cpp-qwen4exp`. It ran on port 8100 with `-ngl 99 -fa on -np 1 -c 65536 --jinja`, no MTP, on the same IQ3_S files.

| | Strata v0.2.6 | llama.cpp `d854d98` | Strata ÷ llama.cpp |
|:--|:--:|:--:|:--:|
| Decode @ 578 / 4K / 8K / 32K / 60K (tok/s) | 74.3 / 70.0 / 67.5 / 70.9 / 66.3 | 40.2 / 39.0 / 38.8 / 36.9 / 35.2 | **1.74–1.92×** |
| Cold prefill ~4K / ~25–33K / ~27K-on-32K (tok/s) | 741 / 786 / 755 | 676 / 653 / 628 | 1.10–1.20× |
| API smoke | 5/5, multi-turn 4.83 s | 5/5, multi-turn 6.86 s | — |
| OpenCode browse (median) | 20.95 s | **9.67 s** (8.14–12.56) | 0.46× |
| OpenCode search (median) | 24.94 s | **14.84 s** (11.56–34.53) | 0.60× |

- **Strata decodes about 1.8× faster.** The decode ratio matches upstream's M5 Max result.
- **llama.cpp still wins the OpenCode loop by 1.7–2.2×.** Its slot cache matches the system prompt by LCP similarity even after the title request, so turn 1 reads 4 new tokens instead of ~11.9K.
- **Use Strata for long single conversations and generation-heavy work.** For agent clients that start many short sessions, llama.cpp currently wins.

Raw JSON: [`docs/models/benchmarks/logs/qwen38-flash-next-iq3s/`](../../models/benchmarks/logs/qwen38-flash-next-iq3s/).

## Known limitations

- **One model family.** The Mac engine runs Qwen3.8-Flash-Next (the original, Unsloth UD and agentionai Gyro). Swift 1.5 and the Coder are not set up for Mac yet, and Qwen3.6 and DeepSeek V4.1 do not run on the Metal engine.
- **One request at a time.** `--parallel` is not ported to Metal.
- **The prompt cache keeps only the live session (observed in v0.2.6 on Metal).** Any other request between two calls (for example OpenCode's title call) throws the cached prefix away, so each new agent session re-reads its whole system prompt: about 15.6 s for 11.9K tokens. llama.cpp's slot cache does not have this problem, and wins the OpenCode loop (see above). The root cause was not investigated; worth an upstream report.
- **One unexplained failure.** Right after one restart, two OpenCode runs hit the 300 s wall with 0 turns, and no request reached the server. A direct curl and an immediate rerun were clean.
- **Context measured to 60K here** (upstream: 32K on Macs). The model's 262K is settable but unmeasured; KV and checkpoint memory grow with `--max-context`, and IQ3_S has only about 4.5 GB of headroom.
- **Not an M5.** Upstream measures on an M5 Max, an M4 Mac mini and an M1 Max. The M3 Ultra was untested before this deploy. Expect about 0.6× the M5 Max on prefill.
- **Lab techniques do not apply**: no JANG / JANGTQ / TurboQuant KV / DFlash / `bailing_hybrid`.
- **DNS-rebinding guard**: an LAN request without `STRATA_ALLOWED_HOSTS` (or an API key) gets 403.
- **Never run another model beside it**, and never run setup's repack beside a running engine: the engine refuses (`STRATA_METAL_IGNORE_REPACK`), because it froze upstream's Mac.
- **Fast-moving upstream**: v0.2.5 and v0.2.6 both shipped on 2026-10-25. Pin a tag and upgrade on purpose.

## Updating

```bash
ssh macstudio "pkill -f 'serve/server.py --engine strata'; cd ~/Strata && git fetch --depth 1 origin tag <NEW_TAG> && \
  git checkout <NEW_TAG> && ./setup.sh --build --no-start --yes"
```

Setup keeps the model files and rewrites only the keys it owns in `strata-iq3_s.json`. Engine args added by hand must be added again.

## See also

- Per-model notes: [`docs/models/per-model/model-summary-qwen-3-8-flash-next.md`](../../models/per-model/model-summary-qwen-3-8-flash-next.md)
- Catalog entry: [`docs/models/model-summary.md`](../../models/model-summary.md#qwen38-flash-next-125b-moe-strata)
- Deploy plan: [`plans/done/plan-strata-macstudio-deploy.md`](../../../plans/done/plan-strata-macstudio-deploy.md)
- Engine repo: [`Niko1221/Strata`](https://github.com/Niko1221/Strata), Mac notes in its [`docs/MAC.md`](https://github.com/Niko1221/Strata/blob/main/docs/MAC.md)
- GGUF repo: [`ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF`](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF)
- Official model: [`Qwen/Qwen3.8-Flash-Next`](https://huggingface.co/Qwen/Qwen3.8-Flash-Next)
