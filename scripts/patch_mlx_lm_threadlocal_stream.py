#!/usr/bin/env python3
"""
Patch mlx_lm/generate.py to lazily create generation_stream per thread.

The stock module-level expression `mx.new_thread_local_stream(...)` runs on the
main thread at import time, but vllm-mlx and mlx-openai-server both run inference
in worker threads, where that stream object is invalid → "There is no Stream(gpu, 1)
in current thread". Models that use multiple Metal kernels / streams (e.g. the
bailing_hybrid hybrid attention) trip this consistently.

Fix: convert `generation_stream` into a thread-local lazy accessor and turn
all bare references `generation_stream` into calls `generation_stream()`.
Idempotent: skips when sentinel comment is present.
"""
import re
import sys
from pathlib import Path


SENTINEL = "# THREAD_LOCAL_STREAM_PATCH_APPLIED"

OLD_DEF = "generation_stream = mx.new_thread_local_stream(mx.default_device())"
NEW_DEF = f"""# A stream on the default device just for generation
{SENTINEL}
import threading as _gs_threading
_gs_tls = _gs_threading.local()
def generation_stream():
    s = getattr(_gs_tls, "stream", None)
    if s is None:
        s = mx.new_stream(mx.default_device())
        _gs_tls.stream = s
    return s"""


def patch_file(path: Path) -> bool:
    src = path.read_text()
    if SENTINEL in src:
        print(f"[skip] {path} already patched", flush=True)
        return False
    if OLD_DEF not in src:
        print(f"[skip] {path} does not contain expected stream definition", flush=True)
        return False

    # 1. Replace the module-level definition (and the comment line above it)
    src = src.replace(
        f"# A stream on the default device just for generation\n{OLD_DEF}",
        NEW_DEF,
    )

    # 2. Convert bare references to calls. Match `generation_stream` not already
    # followed by `(` and not inside the new definition we just inserted.
    def repl(match):
        return "generation_stream()"

    # All remaining occurrences after the new definition block.
    head, sep, tail = src.partition(NEW_DEF)
    # In `tail`, transform every standalone reference.
    tail = re.sub(r"\bgeneration_stream\b(?!\()", "generation_stream()", tail)
    src = head + sep + tail

    path.write_text(src)
    print(f"[ok] patched {path}", flush=True)
    return True


def main():
    if len(sys.argv) < 2:
        print("usage: patch_mlx_lm_threadlocal_stream.py <path/to/mlx_lm/generate.py> [...]", file=sys.stderr)
        sys.exit(2)
    for p in sys.argv[1:]:
        patch_file(Path(p))


if __name__ == "__main__":
    main()
