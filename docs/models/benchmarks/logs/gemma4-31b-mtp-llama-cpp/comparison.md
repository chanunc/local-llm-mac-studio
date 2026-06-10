# Gemma 4 31B MTP on mainline llama.cpp (`961e9a3`)

Date: 2026-06-09

## Dense Gemma 4 31B Q4_K_M

Baseline server:

- Model alias: `gemma4-31b-q4km-baseline`
- Binary: out-of-tree candidate build from `ggml-org/llama.cpp` commit `961e9a3`
- No speculative decoding

Speculative variants:

- `gemma4-31b-q4km-mtp-n1`
- `gemma4-31b-q4km-mtp-n2`
- `gemma4-31b-q4km-mtp-n4`

### Decode throughput

| Context | Baseline | MTP n=1 | Delta | MTP n=2 | MTP n=4 |
|:--|--:|--:|--:|--:|--:|
| 512 | 29.89 | **33.51** | **+12.1%** | 31.85 | 23.76 |
| 4096 | 28.61 | **32.07** | **+12.1%** | 28.81 | 20.24 |
| 8192 | 27.84 | **32.02** | **+15.0%** | 28.98 | 21.11 |
| 32768 | 23.75 | **25.44** | **+7.1%** | 23.39 | 17.27 |

Observed winner: `n=1`.

### Correctness

- Baseline tool smoke: `5/5`, multi-turn `16.0s`
- MTP `n=1` tool smoke: `5/5`, multi-turn `14.62s`
- Direct one-shot MTP probe: `draft_n=41`, `draft_n_accepted=38` (92.7% acceptance on the sampled request)

### Agent loop

| Scenario | Baseline | MTP n=1 | Delta |
|:--|--:|--:|--:|
| Browse `www.example.com` | 15.39 s | **13.75 s** | **-10.7%** |
| Search `Hackernews latest topic` | **38.20 s** | 39.45 s | +3.3% |

Interpretation:

- Browse improved enough to meet the plan's 10% agent threshold.
- Search did not improve on median and still produced one long 3-turn warmup outlier.
- MTP helps dense decode, but the gain is not large enough to guarantee a win on every short-output agent loop.

## Qwen3.6 27B regression guard

Model alias: `qwen3.6-27b-mtp-ud-q6kxl`

Validated against the preserved old binary on the same machine:

| Surface | `510b5c2` baseline | `961e9a3` candidate | Delta |
|:--|--:|--:|--:|
| Tool smoke pass rate | 5/5 | 5/5 | none |
| Tool multi-turn total | 20.91 s | **19.26 s** | **-7.9%** |
| Real-prompt decode @ 512 | 26.10 tok/s | **27.17 tok/s** | **+4.1%** |
| Real-prompt decode @ 8192 | 23.98 tok/s | **25.58 tok/s** | **+6.7%** |

The regression only showed up on the OpenCode browse loop, and it was stable across reruns:

- `510b5c2` browse run: **28.38 s**
- `961e9a3` browse run 1: **56.62 s**
- `961e9a3` browse run 2: **59.93 s**

The candidate did not fail correctness. It changed behavior in a way that made the browse flow much heavier: the baseline run used **118 input tokens** total, while both candidate runs expanded to about **8.9K input tokens** on the first turn before `webfetch` completed. That is enough to make the upgraded binary a bad default for the existing Qwen MTP sidecar even though its microbench numbers are better.

Decision:

- **Do not keep `961e9a3` as the default `~/llama-cpp-mainline/build/bin/llama-server`.**
- Keep the source tree and out-of-tree candidate build for Gemma follow-up work, but leave the default executable on `510b5c2`.

## Practical result

- Gemma 4 31B dense + external assistant is viable on Apple Silicon mainline llama.cpp.
- Best tested depth here was `--spec-draft-n-max 1`, not `4`.
- The upgrade is useful as an experiment branch for Gemma, but not yet a drop-in replacement for the existing Qwen MTP sidecar on this machine.
