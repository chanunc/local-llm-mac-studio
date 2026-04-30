# Model Summary: MiMo V2.5 (130-expert pruned, q-head, 4-bit)

Xiaomi's `MiMoV2ForCausalLM` (`mimo_v2`) — a sparse MoE pruned from the full MiMo-V2.5 checkpoint by `jedisct1` to keep only the first 130 experts per layer plus a quantized head. ~80 GB on disk, 4-bit MLX uniform quant, multimodal input support in the chat template (text + vision + audio pads) but text-only output via vllm-mlx. Default thinking ON (`<think>`). Deployed 2026-04-30.

| Spec | Value |
|:-----|:------|
| HuggingFace | [jedisct1/MiMo-V2.5-MLX-4bit-first130experts-qhead](https://huggingface.co/jedisct1/MiMo-V2.5-MLX-4bit-first130experts-qhead) |
| Base | [XiaomiMiMo/MiMo-V2.5](https://huggingface.co/XiaomiMiMo/MiMo-V2.5) |
| Architecture | `MiMoV2ForCausalLM`, `model_type=mimo_v2` |
| Quant | 4-bit uniform MLX (`group_size=64`) |
| Pruning | first 130 experts kept per layer (from a much larger expert pool); `expert_keep_indices` in config maps survivors |
| On-disk size | ~80 GB |
| Tool-call format | Hermes-style `<tool_call><function=name><parameter=k>v</parameter></function></tool_call>` (same XML body as Qwen3-coder, wrapped in `<tool_call>` tags) |
| Reasoning | `<think>…</think>` blocks (parsed by `--reasoning-parser qwen3`) |
| Multimodality | Vision + audio + video pads in chat template; vllm-mlx loads text-only |

**vllm-mlx model ID:** `jedisct1/MiMo-V2.5-MLX-4bit-first130experts-qhead`

## Deploying to vllm-mlx

This model needs **PR #1219 vendored** before it will load — `mimo_v2` is not in mlx-lm 0.31.3 (only `mimo.py` and `mimo_v2_flash.py` ship; the `mimo_v2.py` for V2.5 is open in PR [ml-explore/mlx-lm#1219](https://github.com/ml-explore/mlx-lm/pull/1219), 556 lines).

```bash
# 1. Vendor mimo_v2.py from PR #1219
curl -sL "https://raw.githubusercontent.com/kernelpool/mlx-lm/add-mimo-v2/mlx_lm/models/mimo_v2.py" -o /tmp/mimo_v2.py
scp /tmp/mimo_v2.py macstudio:/tmp/
ssh macstudio "cp /tmp/mimo_v2.py ~/vllm-mlx-env/lib/python3.12/site-packages/mlx_lm/models/mimo_v2.py"

# 2. Download model (80 GB, ~12 min on a fast connection)
ssh macstudio "~/vllm-mlx-env/bin/hf download jedisct1/MiMo-V2.5-MLX-4bit-first130experts-qhead"

# 3. Launch (no JANG wrapper — standard MLX safetensors)
ssh macstudio "nohup ~/vllm-mlx-env/bin/vllm-mlx serve jedisct1/MiMo-V2.5-MLX-4bit-first130experts-qhead \
  --served-model-name jedisct1/MiMo-V2.5-MLX-4bit-first130experts-qhead \
  --port 8000 --host 0.0.0.0 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  > /tmp/vllm-mlx.log 2>&1 &"
```

The Ling thread-local-stream + inline-gen patches (`scripts/patch_mlx_lm_threadlocal_stream.py`, `scripts/patch_vllm_mlx_inline_gen.py`) were already applied to this venv from the Ling deployment and are sufficient — no MiMo-specific patches needed. Re-apply both after `pip install -U vllm-mlx` or `pip install -U mlx-lm`.

## Benchmarks (2026-04-30)

Full results: [`benchmarks/mimo-v2.5-4bit-130experts/agent-bench.json`](benchmarks/mimo-v2.5-4bit-130experts/agent-bench.json).

### OpenCode end-to-end (`opencode run --format json`)

| Scenario | Wall median | Outcome | Pass rate |
|:---------|:------------|:--------|:---------:|
| Browse www.example.com | 55.51 s ⚠ | 1/3 runs emit invalid tool call, 2/3 hit 8K-token cap before tool | 0/3 |
| Browse Hackernews latest topic | 222.64 s ⛔ | 0/3 runs ever call a tool — model reasons until max_tokens | 0/3 |

### Raw API (`/v1/chat/completions` with single tool)

```json
{"role":"assistant",
 "tool_calls":[{"id":"call_20316b99","type":"function",
                "function":{"name":"webfetch","arguments":"{\"url\": \"www.example.com\"}"}}]}
```

A single-tool prompt produces a clean tool call (45 completion tokens, finish_reason=`tool_calls`). The breakdown is between API-level and OpenCode's 10-tool agent path, not at the server config layer.

## Caveats

- **Not viable as an agent backbone in this stack today.** OpenCode + thinking-on + 10-tool catalog is too much for this pruned variant — model spends all 8192 output tokens reasoning instead of emitting a tool call. JANG_4K (also 35B-A3B sparse) handles the same load in 12-16 s.
- **Heavy expert pruning likely cause.** The base MiMo-V2.5 ships with hundreds of experts; the `first130experts-qhead` cut keeps only the first 130 plus a quantized output head. Experts pruned this aggressively from a fresh base often lose calibration on long-form reasoning + structured output simultaneously.
- **Multimodal inputs unused.** Chat template includes vision/audio/video tokens but vllm-mlx loads as text-only. If multimodal is needed, mlx-vlm with the unpruned base is the path forward.
- **No comparison vs unpruned base.** The full `XiaomiMiMo/MiMo-V2.5-Pro` is multi-host distributed (per the PR description's `mlx.launch jaccl` example), so it doesn't fit the Mac Studio 96 GB single-host constraint. The 130-expert variant is the only single-host MiMo V2.5 path; if it doesn't work for tool-heavy agents, retry with a less aggressive pruning (e.g. `first200experts`) when one becomes available.

## When to use

- **Best fit:** raw API single-tool calls, simple Q&A, exploration of the architecture.
- **Poor fit:** OpenCode / Claude Code agent loops, anything with >3 tools available simultaneously, prompts that do not give an obvious tool route.
