# Qwen Empty-`<think>` Template Patch — Validation

Confirms that the Bug #1 chat-template patch (applied 2026-04-19) eliminates empty `<think></think>` blocks from serialized multi-turn history. Empty blocks break KV-cache prefix matching across all three servers (vllm-mlx, mlx-openai-server, oMLX); worst impact is in agentic / tool-use loops. Source: [r/LocalLLaMA 1sg076h](https://www.reddit.com/r/LocalLLaMA/comments/1sg076h/).

## What was patched

| Model dir | File patched | Pattern |
|---|---|---|
| `JANGQ-AI--Qwen3.5-122B-A10B-JANG_2S` | `tokenizer_config.json` | Qwen 3.5 guard |
| `JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K` | `tokenizer_config.json` | Qwen 3.5 guard |
| `dealignai--Qwen3.5-VL-122B-A10B-4bit-MLX-CRACK` | `tokenizer_config.json` | Qwen 3.5 guard |
| `mlx-community--Qwen3.5-27B-4bit` | `chat_template.jinja` | Qwen 3.5 guard |
| `nightmedia--Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-qx64-hi-mlx` | `chat_template.jinja` | Qwen 3.5 guard |
| `mlx-community/Qwen3.6-35B-A3B-6bit` | `chat_template.jinja` | Qwen 3.6 guard (preserves `preserve_thinking` semantics) |

Backups saved as `.bak.<timestamp>` siblings. Re-apply instructions: [maintenance.md#qwen-empty-think-template-patch](../server/mlx-openai-server/maintenance.md#qwen-empty-think-template-patch).

## Automated template validation (offline)

Renders the patched templates with Jinja2 locally — no running server needed.

```bash
ssh macstudio 'python3 << "PYEOF"
import json, re
from jinja2 import Environment

def render_str(tmpl, msgs, **kw):
    env = Environment()
    env.globals["raise_exception"] = lambda m: (_ for _ in ()).throw(Exception(m))
    return env.from_string(tmpl).render(
        messages=msgs, add_generation_prompt=True,
        bos_token="<|im_start|>", eos_token="<|im_end|>", **kw)

def render_file(path, msgs, **kw):
    return render_str(open(path).read(), msgs, **kw)

def check(label, rendered):
    fail = bool(re.search(r"<think>\s*</think>", rendered))
    print(f"  [{'FAIL' if fail else 'PASS'}] {label}")
    if fail:
        for m in re.finditer(r"<think>.*?</think>", rendered, re.DOTALL):
            print(f"    >> {repr(m.group()[:100])}")

# Tool-use multi-turn: assistant reply with empty reasoning after a tool result
# This is the exact scenario that triggered cache misses pre-patch
msgs = [
    {"role": "user",      "content": "What is 2+2?"},
    {"role": "assistant", "content": "",
     "tool_calls": [{"function": {"name": "calc", "arguments": {"expr": "2+2"}}}],
     "reasoning_content": "I need to use the calculator tool"},
    {"role": "tool",      "content": "4", "tool_call_id": "c1"},
    {"role": "assistant", "content": "The answer is 4", "reasoning_content": ""},
    {"role": "user",      "content": "Thanks, what about 3+3?"},
]

M = "/Users/chanunc/.omlx/models"
cfg35_122 = json.load(open(f"{M}/JANGQ-AI--Qwen3.5-122B-A10B-JANG_2S/tokenizer_config.json"))
cfg35_35  = json.load(open(f"{M}/JANGQ-AI--Qwen3.5-35B-A3B-JANG_4K/tokenizer_config.json"))
cfgVL     = json.load(open(f"{M}/dealignai--Qwen3.5-VL-122B-A10B-4bit-MLX-CRACK/tokenizer_config.json"))

print("=== tool-use multi-turn (exact bug scenario) ===")
check("Qwen3.5-122B JANG 2S",       render_str(cfg35_122["chat_template"], msgs))
check("Qwen3.5-35B JANG 4K",        render_str(cfg35_35["chat_template"], msgs))
check("Qwen3.5-VL CRACK 122B",      render_str(cfgVL["chat_template"], msgs))
check("Qwen3.5-27B mlx-community",  render_file(f"{M}/mlx-community--Qwen3.5-27B-4bit/chat_template.jinja", msgs))
check("nightmedia Opus Distilled",  render_file(f"{M}/nightmedia--Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-qx64-hi-mlx/chat_template.jinja", msgs))
p36 = f"{M}/mlx-community/Qwen3.6-35B-A3B-6bit/chat_template.jinja"
check("Qwen3.6-35B (default)",       render_file(p36, msgs, preserve_thinking=False))
check("Qwen3.6-35B (preserve=True)", render_file(p36, msgs, preserve_thinking=True))
PYEOF'
```

Expected output — all PASS:
```
=== tool-use multi-turn (exact bug scenario) ===
  [PASS] Qwen3.5-122B JANG 2S
  [PASS] Qwen3.5-35B JANG 4K
  [PASS] Qwen3.5-VL CRACK 122B
  [PASS] Qwen3.5-27B mlx-community
  [PASS] nightmedia Opus Distilled
  [PASS] Qwen3.6-35B (default)
  [PASS] Qwen3.6-35B (preserve=True)
```

## Live two-20-digit-numbers test (requires running server)

This is the community-recommended behavioural test. Tests that the model can recall context it reasoned about in a prior turn — relies on stable KV-cache prefix (which the template patch enables).

### Setup

Start whichever server hosts the model you want to test, then substitute `MODEL` and `BASE_URL` below:

```bash
# Example with vllm-mlx (primary)
BASE_URL=http://<MAC_STUDIO_IP>:8000/v1
MODEL=JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S

# Example with mlx-openai-server (Qwen 3.6)
MODEL=mlx-community/Qwen3.6-35B-A3B-6bit
```

### Test script

```bash
python3 << PYEOF
import json, urllib.request

BASE = "http://<MAC_STUDIO_IP>:8000/v1/chat/completions"
MODEL = "JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S"   # change as needed
HEADERS = {"Content-Type": "application/json"}

def chat(messages):
    req = urllib.request.Request(BASE, json.dumps({
        "model": MODEL, "messages": messages,
        "temperature": 0, "max_tokens": 256,
    }).encode(), HEADERS)
    return json.loads(urllib.request.urlopen(req).read())["choices"][0]["message"]

# Turn 1
history = [{"role": "user",
    "content": "Generate exactly two random 20-digit numbers. Only show me the FIRST one — keep the second to yourself."}]
reply1 = chat(history)
history.append(reply1)
print("Turn 1:", reply1["content"].strip())

# Turn 2
history.append({"role": "user", "content": "Now show me the second number you generated."})
reply2 = chat(history)
print("Turn 2:", reply2["content"].strip())
print()

# Check
t2 = reply2["content"]
if any(len(w.strip(".,")) == 20 and w.strip(".,").isdigit() for w in t2.split()):
    print("PASS — model recalled the second 20-digit number")
else:
    print("FAIL — model could not recall (or did not generate) the second number")
PYEOF
```

### Pass criteria

| Turn | Expected |
|---|---|
| Turn 1 | Model shows exactly one 20-digit number |
| Turn 2 | Model recalls a distinct 20-digit number (without re-generating) |

**FAIL** signs: "I don't have a second number", "I only generated one", or generating a brand-new number rather than recalling the original. This indicates the `<think>` blocks in the prior turn still differ between requests, causing a cache miss and context loss.

## Results

| Date | Model | Validation method | Result |
|---|---|---|---|
| 2026-04-19 | All 6 Qwen 3.5/3.6 models | Jinja offline render (tool-use scenario) | All PASS |
| — | All 6 models | Live two-20-digit-numbers test | Pending (server start required) |
