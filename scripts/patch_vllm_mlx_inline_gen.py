#!/usr/bin/env python3
"""
Patch vllm-mlx to run generation on the asyncio event loop thread instead of
via `asyncio.to_thread`.

Why: MLX streams and Metal kernels are bound to the thread that created them.
mlx-lm models loaded on the main thread cannot be invoked from worker threads —
custom-kernel models like bailing_hybrid (Ling-2.6-flash) crash with
"There is no Stream(gpu, 0) in current thread" when generation runs in a worker.

This patch swaps every `await asyncio.to_thread(callable, ...)` for a direct
call. Generation now blocks the event loop, which is fine for single-stream
inference servers — the loop has nothing else useful to do during a forward
pass anyway.

Idempotent: skips already-patched files via sentinel comment.
"""
import re
import sys
from pathlib import Path


SENTINEL = "# VLLM_MLX_INLINE_GEN_PATCH_APPLIED"


def patch_file(path: Path) -> bool:
    src = path.read_text()
    if SENTINEL in src:
        print(f"[skip] {path} already patched", flush=True)
        return False

    # Replace `await asyncio.to_thread(\n  callable,` with direct sync call
    # Pattern: `await asyncio.to_thread(\n<ws>callable,\n<ws>arg1,\n...\n<ws>)`
    # → `callable(\n<ws>arg1,\n...\n<ws>)`
    pattern = re.compile(
        r"await\s+asyncio\.to_thread\(\s*\n(\s*)([\w.\[\]_]+(?:\.\w+)*)\s*,\s*\n",
        re.MULTILINE,
    )

    def repl(match):
        indent = match.group(1)
        callable_expr = match.group(2)
        return f"{callable_expr}(\n{indent}"

    new_src, n = pattern.subn(repl, src)

    # Also handle short form: `await asyncio.to_thread(callable)`
    pattern2 = re.compile(r"await\s+asyncio\.to_thread\(\s*([\w._]+)\s*\)")
    new_src, n2 = pattern2.subn(r"\1()", new_src)

    if n + n2 == 0:
        print(f"[skip] {path}: no asyncio.to_thread occurrences matched", flush=True)
        return False

    # Insert sentinel near top
    new_src = f"{SENTINEL}\n{new_src}"
    path.write_text(new_src)
    print(f"[ok] patched {path}: {n + n2} substitutions", flush=True)
    return True


def main():
    if len(sys.argv) < 2:
        print("usage: patch_vllm_mlx_inline_gen.py <file.py> [...]", file=sys.stderr)
        sys.exit(2)
    for p in sys.argv[1:]:
        patch_file(Path(p))


if __name__ == "__main__":
    main()
