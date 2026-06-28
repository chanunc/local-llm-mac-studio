# DeepSpec MTP Deployability Check and Long-Context MTP Retest

Date: 2026-06-27

## Upstream DeepSpec finding

DeepSpec is not a deployable OpenAI-compatible inference server. The upstream README describes a three-stage offline workflow: data preparation, training, and evaluation. It requires a trained draft checkpoint before evaluation, and the example evaluation command takes both `target_name_or_path` and `draft_name_or_path`.

The public configs cover:

- Gemma 4 12B: DSpark, DFlash, Eagle3 configs targeting `google/gemma-4-12B-it`.
- Qwen3: 4B, 8B, 14B configs.

The public configs do not cover Gemma 4 31B or Qwen3.6. DeepSpec also warns that the default `Qwen/Qwen3-4B` target cache is about 38 TB, and the training launcher defaults to eight CUDA-visible GPUs. On the Mac Studio, this makes DeepSpec a research/training source, not a runtime to install for this lab.

Deployable runtime used for actual tests:

- Gemma assistant MTP: mainline `llama.cpp` `draft-mtp` with `-md <assistant.gguf>`.
- Qwen3.6 native MTP: mainline `llama.cpp` `draft-mtp` using bundled MTP heads in the GGUF.
- TurboQuant fork: rejected for Gemma assistant MTP because its help output exposes `-md` but does not expose the `draft-mtp` speculative type.

## Results

| Order | Model | DeepSpec support | Runtime tested | Result |
|:--|:--|:--|:--|:--|
| 1 | Gemma 4 31B dense Q4_K_M + Q8_0 assistant | No public DeepSpec config/checkpoint | `llama.cpp` mainline `ac4cdde`, `-c 262144`, `draft-mtp n=1` | Loaded at 262K and initialized `draft-mtp`; 128K probe aborted after 142.8 s at 30,728 tokens, effective prefill down to 215 tok/s. Not practical for 128K API bench in this rig. |
| 2 | yuxinlu1 Gemma 4 12B Agentic v2 Q8_0 + MTP Q8_0 assistant | DeepSpec has Gemma 4 12B training configs, but no shipped checkpoint/runtime | `llama.cpp` mainline `ac4cdde`, `-c 262144`, `draft-mtp n=1` | Loaded at 262K. Cold 128K probe: 131,103 tokens in 393.52 s = 333 tok/s. Cache-warm measured decode: 40.67 tok/s, draft acceptance 7/7. Raw: `api-server-mainline-mtp-n1-128k-20260627.json`. |
| 3a | Huihui Qwen3.6 35B-A3B MTP Q6_K | No DeepSpec Qwen3.6 config; native Qwen MTP heads already in GGUF | `llama.cpp` mainline `ac4cdde`, `-c 262144`, `draft-mtp n=2` | Best fit. Cold 128K probe: 131,096 tokens in 187.37 s = 699.65 tok/s. Cache-warm 128K decode: 33.22 tok/s, draft acceptance 9/10. 260K probe: 260,024 prompt tokens; cold extension from 128K took 461.49 s for 129,444 new tokens = 280.49 tok/s. Cache-warm 260K decode: 17.30 tok/s, draft acceptance 9/10. |
| 3b | llmfan46 Qwen3.6 27B Heretic v2 MTP Q6_K | No DeepSpec Qwen3.6 config; native Qwen MTP heads preserved in GGUF | `llama.cpp` mainline `ac4cdde`, `-c 131072`, `draft-mtp n=2` | Loaded at 131K. Exact 131,072 request failed because template overhead made 131,096 tokens. Near-128K probe (`130000`) timed out at 600 s after 116,736 processed tokens, effective prefill 194.5 tok/s. Not practical for 128K API bench in this rig. |

## Raw Files

- `../gemma4-12b-agentic-v2-q8-turbo3-256k/api-server-mainline-mtp-n1-128k-20260627.json`
- `../qwen36-mtp-longctx/api-server-huihui-35b-mtp-128k-20260627.json`
- `../qwen36-mtp-longctx/api-server-huihui-35b-mtp-260k-20260627.json`

## Practical Conclusion

DeepSpec does not add a deployable MTP path for any recorded model today. It is useful as evidence that DeepSeek is training/evaluating Gemma/Qwen-family speculative drafters, but it cannot be installed as a serving runtime on this Mac Studio without first producing a trained draft checkpoint.

For deployed models, mainline `llama.cpp` is the valid runtime:

- Gemma 4 12B can use the shipped Gemma assistant draft and does benefit in decode, but 128K cold prefill is slow.
- Gemma 4 31B can load the assistant at 262K, but 128K cold prefill is too slow to be useful.
- Huihui Qwen3.6 35B-A3B MTP is the only recorded model here that remains plausible at 128K-260K.
- Dense Qwen3.6 27B MTP variants are operational but poor long-context candidates under this benchmark.
