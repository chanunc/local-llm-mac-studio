# Scripts

Small operational helpers for patching local server packages, switching client config, and running benchmarks.

## Benchmarks

| Script | Purpose |
|:--|:--|
| [`bench_api_server.py`](bench_api_server.py) | Streaming `/v1/chat/completions` throughput, TTFT, and prefill benchmark |
| [`bench_api_tool_call.py`](bench_api_tool_call.py) | API-level tool-call harness for OpenAI-compatible servers |
| [`bench_agent_tool_call.py`](bench_agent_tool_call.py) | End-to-end OpenCode/Pi-style agent loop benchmark |

## Patches

| Script | Target |
|:--|:--|
| [`patch_omlx_cache.py`](patch_omlx_cache.py) | oMLX per-model hot cache support |
| [`patch_mlx_lm_threadlocal_stream.py`](patch_mlx_lm_threadlocal_stream.py) | mlx-lm generation stream thread-local fix |
| [`patch_vllm_mlx_inline_gen.py`](patch_vllm_mlx_inline_gen.py) | vllm-mlx inline generation fix for thread-bound MLX kernels |
| [`patch_vllm_mlx_log_level.py`](patch_vllm_mlx_log_level.py) | vllm-mlx `VLLM_MLX_LOG_LEVEL` support |
| [`patch_vllm_mlx_streaming_tools.py`](patch_vllm_mlx_streaming_tools.py) | vllm-mlx streaming tool-call parsing fix |
| [`patch_mlx_openai_tool_args.py`](patch_mlx_openai_tool_args.py) | mlx-openai-server stringified tool-call argument fix |
| [`patch_vmlx_jangtq_mllm_tools.py`](patch_vmlx_jangtq_mllm_tools.py) | vmlx MLLM tool-template and replay fixes |

## Client Config

| Script | Purpose |
|:--|:--|
| [`switch_opencode_config.py`](switch_opencode_config.py) | Swap local OpenCode config between server templates |

Patch scripts target packages installed on the Mac Studio. Re-run them after upstream package upgrades when the relevant runbook says so.
