# JANG — Adaptive Mixed-Precision Quantisation

[JANG](https://jangq.ai/) is a quantisation format from [JANGQ-AI](https://github.com/jjang-ai/jangq) that assigns **different bit widths per layer** based on sensitivity analysis. Attention layers typically get 6-8 bit precision while MoE expert layers drop to 2-4 bit. The result is **~48% smaller on disk than uniform MLX 8-bit** with minimal quality loss.

JANG is **a weight format**, not a generation-time technique. Once loaded, the model runs through stock `mlx_lm` generation with no runtime overhead.

## Format properties

- **Custom weight format** — JANG safetensors with metadata describing per-layer bit assignments. Cannot be loaded by stock `mlx_lm.load()`; needs `jang_tools.load_jang_model()`.
- **Instant mmap load** — memory-mapped weights load in **<1 s** vs 5-15 s for standard MLX safetensors.
- **Same inference path post-load** — model class is identical (e.g. `mlx_lm.models.qwen3_5_moe.Model`); only the weight loader differs.
- **Loader package** — `pip install 'jang[mlx]>=0.1.0'` ships `jang_tools.loader.is_jang_model()` and `load_jang_model()`. Public pypi has these (unlike JANGTQ, see [`model-quantization-turboquant.md`](model-quantization-turboquant.md)).

## How servers integrate JANG

Three servers in this repo support JANG via different mechanisms. The shared problem: every server's bootstrap funnels through `mlx_lm.load()` which only knows safetensors. The fix in two cases is the same monkey-patch shape:

```python
import mlx_lm
_orig_load = mlx_lm.load

def patched_load(path_or_hf_repo, tokenizer_config=None, **kwargs):
    from jang_tools.loader import is_jang_model, load_jang_model
    if is_jang_model(str(path_or_hf_repo)):
        return load_jang_model(str(path_or_hf_repo))
    return _orig_load(path_or_hf_repo, tokenizer_config=tokenizer_config, **kwargs)

mlx_lm.load = patched_load
```

| Server | Integration approach | Detail doc |
|:--|:--|:--|
| **oMLX** | Fork overlay ([AlexTzk/omlx PR #364](https://github.com/jundot/omlx/pull/364)) — adds `omlx/engine/jang.py` (`JANGLoader`, ~675 lines) so JANG metadata is detected at model-discovery time. Pip-installed over the Homebrew base, with the original at `omlx.bak`. | [`../../servers/omlx/jang-fork.md`](../../servers/omlx/jang-fork.md) |
| **mlx-lm.server** | Wrapper script (`run_mlx_server_jang.py`) monkey-patches `mlx_lm.load` and `mlx_lm.utils.load`, then invokes `mlx_lm.server.main()`. | [`../../servers/mlx-lm/jang-patch.md`](../../servers/mlx-lm/jang-patch.md) |
| **vllm-mlx** | Same monkey-patch wrapper (`run_vllm_jang.py`) — needed because `vllm_mlx.utils.tokenizer.load_model_with_fallback()` calls `mlx_lm.load` internally. v0.2.6 also needs a tokenizer.py return-statement fix. | [`../../servers/vllm-mlx/jang-patch.md`](../../servers/vllm-mlx/jang-patch.md) |

`vmlx` does not need a JANG-specific patch — its bundled Python ships `jang_tools` natively, but it is reserved for JANGTQ workloads; do not use it for plain JANG models.

## Cross-server performance (Qwen3.5-35B-A3B JANG 4K, 32K context)

| Server | Gen tok/s | vs oMLX baseline |
|:--|--:|--:|
| `vllm-mlx` + JANG patch | **83.8** | +40% |
| `mlx-lm.server` + JANG patch | 77.6 | +30% |
| `oMLX` + JANG fork | 59.9 | baseline |

`vllm-mlx` wins because it does not run prompt-cache prefill on a separate thread (which JANG's loader is fine with but oMLX's pool re-creates per request). Detailed cross-server numbers: [`../benchmarks/model-benchmark-api-server.md`](../benchmarks/model-benchmark-api-server.md).

## Stacks with TurboQuant

JANG (weight quantisation) and TurboQuant (KV cache compression) are independent. They stack: `JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K` + TurboQuant 3.5-bit shows the same KV compression ratio (3.0x at 32K, 3.4x at 64K) as `mlx-community/Qwen3.5-35B-A3B-4bit` + TurboQuant — the bottleneck is in KV operations, not weight access. See [`model-quantization-turboquant.md`](model-quantization-turboquant.md) for the full benchmark.

## Known limitations

- **JANG + Nemotron-H architecture** — JANG-quantised models with Nemotron-H (Mamba-2 + latent MoE gate) fail with `[matmul] shape mismatch` at the expert router gate. PR #364's weight mapping is buggy for latent MoE projections. Affects `JANGQ-AI/Nemotron-Cascade-2-30B-A3B-JANG_4M` and `JANGQ-AI/Nemotron-3-Super-120B-A12B-JANG_4M`. Workaround: use MLX nvfp4/mxfp4 quantisations for Nemotron models. Non-Nemotron JANG models (Qwen3.5 family) work fine.
- **Unreviewed code** — the AlexTzk fork has not been merged upstream into `jundot/omlx`. JANG loader code is unreviewed by oMLX maintainers.
- **Homebrew upgrade overwrites the fork** — `brew upgrade omlx` reverts to stock; re-apply the fork + cache patches after every upgrade. Recipe: [`../../servers/omlx/jang-fork.md` § Maintenance](../../servers/omlx/jang-fork.md#maintenance-after-upgrades).
- **Wrapper-script servers report model name as full path** — `mlx-lm.server` and `vllm-mlx` JANG-wrapper modes use the local filesystem path as the API model ID. Clients must use the path string, not a clean HF-style name.
- **Single-model only on wrapper servers** — `mlx-lm.server` and `vllm-mlx` JANG wrappers load one model at startup; no hot-swapping. Use oMLX if you need multiple JANG models live.
- **`prompt_tokens=0` field-fill bug on vllm-mlx** — vllm-mlx 0.2.6 reports `usage.prompt_tokens=0` for JANG models in both streaming and non-streaming responses. Compute prefill rates from the model's tokeniser instead.

## Currently deployed JANG models

| Model | Format | Server | On-disk | Status |
|:--|:--|:--|--:|:--|
| [`JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K`](https://huggingface.co/JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K) | JANG 4-bit avg | mlx-openai-server (multi-model YAML) | 19 GB | Active |
| [`JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S`](https://huggingface.co/JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S) | JANG 2-bit | (downloaded, not in current roster) | 35 GB | Available |
| [`JANGQ-AI/Qwen3.6-27B-JANG_4M`](https://huggingface.co/JANGQ-AI/Qwen3.6-27B-JANG_4M) | JANG 4-bit | vllm-mlx (previous primary) | 14 GB | Available |

Live roster reference: [`../../current.md`](../../current.md).

## See also

- [`../../servers/omlx/jang-fork.md`](../../servers/omlx/jang-fork.md) — oMLX fork overlay (PR #364)
- [`../../servers/mlx-lm/jang-patch.md`](../../servers/mlx-lm/jang-patch.md) — `mlx-lm.server` wrapper
- [`../../servers/vllm-mlx/jang-patch.md`](../../servers/vllm-mlx/jang-patch.md) — `vllm-mlx` wrapper
- [`../benchmarks/model-benchmark-turboquant-jang.md`](../benchmarks/model-benchmark-turboquant-jang.md) — JANG ⊥ TurboQuant stacking benchmark
- [`model-quantization-turboquant.md`](model-quantization-turboquant.md) — TurboQuant + JANGTQ technique notes
- [JANGQ-AI on Hugging Face](https://huggingface.co/JANGQ-AI) — model index
- [`jjang-ai/jangq`](https://github.com/jjang-ai/jangq) — upstream loader source
