"""Patch dflash-mlx serve.py to bind on 0.0.0.0 instead of 127.0.0.1.

Why: dflash-mlx 0.1.0 (`pip install dflash-mlx`) hard-codes the HTTPServer
bind address to "127.0.0.1" with no --host flag, so LAN clients on the
Mac Studio's other interfaces cannot reach the server. This patch is
idempotent and re-applies cleanly after `pip install -U dflash-mlx`.

Run on the Mac Studio:
    ~/dflash-mlx-env/bin/python ~/setup-llm-macstu/scripts/patches/patch_dflash_mlx_host.py
"""

import sys
from pathlib import Path


OLD = '("127.0.0.1", int(args.port))'
NEW = '("0.0.0.0", int(args.port))'
SENTINEL = '("0.0.0.0", int(args.port))'


def find_serve_py() -> Path:
    try:
        import dflash_mlx
    except ImportError:
        print("Error: dflash_mlx not importable. Activate ~/dflash-mlx-env first.", file=sys.stderr)
        sys.exit(1)
    pkg_dir = Path(dflash_mlx.__file__).parent
    serve_py = pkg_dir / "serve.py"
    if not serve_py.exists():
        print(f"Error: {serve_py} not found.", file=sys.stderr)
        sys.exit(1)
    return serve_py


def main() -> int:
    serve_py = find_serve_py()
    text = serve_py.read_text()

    if SENTINEL in text:
        print(f"{serve_py} is already patched (binds on 0.0.0.0).")
        return 0

    if OLD not in text:
        print(
            f"Error: Could not find expected bind line in {serve_py}.\n"
            f"  Expected: {OLD}\n"
            "  Likely cause: dflash-mlx version drift. Inspect serve.py and update this script.",
            file=sys.stderr,
        )
        return 1

    serve_py.write_text(text.replace(OLD, NEW))
    print(f"Patched {serve_py}: bind 127.0.0.1 -> 0.0.0.0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
