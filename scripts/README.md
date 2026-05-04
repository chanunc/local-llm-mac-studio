# Scripts

Operational helpers split by purpose: benchmark drivers, server-package patches, and client-config switching.

## Layout

| Subdir | Purpose |
|:--|:--|
| [`bench/`](bench/) | Benchmark drivers (run from any client; output lands under `docs/models/benchmarks/<model>/`). |
| [`patches/`](patches/) | Monkey-patches for installed server packages on the Mac Studio. Re-run after upstream upgrades. |
| `switch_opencode_config.py` | Local-only helper that swaps OpenCode's config between server templates in `configs/clients/`. |
| `chk_llm_macstu.py` | Probes the Mac Studio over SSH and reports which LLM server + model is currently running on ports 8000 / 1234 / 8098. |

## Status Checks

| Script | Purpose |
|:--|:--|
| [`chk_llm_macstu.py`](chk_llm_macstu.py) | Probes the Mac Studio over SSH and reports which LLM server + model is currently running on ports 8000 / 1234 / 8098. Supports `--client {opencode,pi,openclaw,qwen-code,claude-code,all}` to emit the matching client config for the detected server, `--logs` to emit the per-server log-tail command, and `--all` to bundle status + all client configs + log command into one copy-friendly text block (or `--all --json` for a machine-readable object). |

Useful as the **Event 4 pre-benchmark hygiene** primitive — see [the Sync Policy](../CLAUDE.md#event-4-running-a-new-benchmark) for the full clean-machine recipe.

## Benchmarks

| Script | Purpose |
|:--|:--|
| [`bench/bench_api_server.py`](bench/bench_api_server.py) | Streaming `/v1/chat/completions` throughput, TTFT, and prefill benchmark (recognizes `delta.content` / `delta.reasoning_content` / `delta.reasoning` for TTFT — last is mlx-lm-server naming used by dflash-mlx) |
| [`bench/bench_api_tool_call.py`](bench/bench_api_tool_call.py) | API-level tool-call harness for OpenAI-compatible servers |
| [`bench/bench_agent_tool_call.py`](bench/bench_agent_tool_call.py) | End-to-end OpenCode/Pi-style agent loop benchmark (accepts `--base-url` to override the OpenCode-config-discovered server during health check) |

Save raw output under [`docs/models/benchmarks/<model-slug>/`](../docs/models/benchmarks/) per the [Sync Policy](../CLAUDE.md#sync-policy-read-this-first-when-changing-live-state).

## Patches

Run on the Mac Studio (`ssh macstudio`) against the live venvs.

| Script | Target |
|:--|:--|
| [`patches/patch_omlx_cache.py`](patches/patch_omlx_cache.py) | oMLX per-model hot cache support |
| [`patches/patch_mlx_lm_threadlocal_stream.py`](patches/patch_mlx_lm_threadlocal_stream.py) | mlx-lm generation stream thread-local fix |
| [`patches/patch_vllm_mlx_inline_gen.py`](patches/patch_vllm_mlx_inline_gen.py) | vllm-mlx inline generation fix for thread-bound MLX kernels |
| [`patches/patch_vllm_mlx_log_level.py`](patches/patch_vllm_mlx_log_level.py) | vllm-mlx `VLLM_MLX_LOG_LEVEL` support |
| [`patches/patch_vllm_mlx_streaming_tools.py`](patches/patch_vllm_mlx_streaming_tools.py) | vllm-mlx streaming tool-call parsing fix |
| [`patches/patch_mlx_openai_tool_args.py`](patches/patch_mlx_openai_tool_args.py) | mlx-openai-server stringified tool-call argument fix |
| [`patches/patch_vmlx_jangtq_mllm_tools.py`](patches/patch_vmlx_jangtq_mllm_tools.py) | vmlx MLLM tool-template and replay fixes |
| [`patches/patch_dflash_mlx_serve.py`](patches/patch_dflash_mlx_serve.py) | dflash-mlx 0.1.4.1+ `default_model_map` + lazy-load banner fixes |
| [`patches/patch_mlx_lm_match.py`](patches/patch_mlx_lm_match.py) | mlx-lm tool-detection state machine reset on terminal `s is None` |
| [`patches/patch_dflash_mlx_host.py`](patches/patch_dflash_mlx_host.py) | dflash-mlx 0.1.0 only — bind 0.0.0.0 (obsoleted by `--host` in 0.1.4.1+) |

Each patch is idempotent. Re-run after `pip install -U <package>`, `brew upgrade <pkg>`, or an MLX Studio DMG update — see the relevant runbook in [`docs/servers/`](../docs/servers/) for exact triggers.
