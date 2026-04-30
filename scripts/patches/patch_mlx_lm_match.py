"""Patch mlx-lm `match()` to handle None state in tool-detection trie.

Why: mlx-lm 0.31.3's `generate.py` ToolDetector.match() blows up with
`KeyError: None` after a tool-call match completes. When the trie reaches
a terminal state, `s` becomes None; the next call does
`states[s][0]` -> KeyError. Reproducible against any tool-calling
benchmark that drives the same conversation through more than one
completion (e.g. `bench_api_tool_call.py` running 5 single-call
scenarios in sequence).

Fix: when `s is None` at entry, reset to the trie's initial state.
This is a forward-only patch — terminal-then-restart behaviour matches
what every other tool-call detector does.

Discovered while running Phase 4 of the dflash-mlx benchmark plan
(plans/done/plan-dflash-mlx-deploy.md). Not specific to dflash-mlx —
any client of mlx-lm's tool-detection state machine hits this.

Run on the Mac Studio (against the venv that has mlx-lm installed):
    ~/dflash-mlx-env/bin/python ~/setup-llm-macstu/scripts/patches/patch_mlx_lm_match.py
"""

import sys
from pathlib import Path


OLD = (
    "    @staticmethod\n"
    "    def match(state, x):\n"
    "        s, n, states = state\n"
    "        n = _step_trie(n, states[s][0], x)"
)
NEW = (
    "    @staticmethod\n"
    "    def match(state, x):\n"
    "        s, n, states = state\n"
    "        if s is None:\n"
    "            # PATCH: terminal state from prior match -- reset to initial\n"
    "            s = next(iter(states))\n"
    "            n = states[s][0]\n"
    "        n = _step_trie(n, states[s][0], x)"
)


def find_generate_py() -> Path:
    try:
        import mlx_lm
    except ImportError:
        print("Error: mlx_lm not importable. Activate the relevant venv first.", file=sys.stderr)
        sys.exit(1)
    pkg_dir = Path(mlx_lm.__file__).parent
    gen_py = pkg_dir / "generate.py"
    if not gen_py.exists():
        print(f"Error: {gen_py} not found.", file=sys.stderr)
        sys.exit(1)
    return gen_py


def main() -> int:
    gen_py = find_generate_py()
    text = gen_py.read_text()

    # Tolerant idempotence check: any prior application of this fix leaves the
    # `if s is None:` reset block, regardless of comment dash style or whitespace.
    if "PATCH: terminal state from prior match" in text or (
        "if s is None:" in text and "next(iter(states))" in text and "n = states[s][0]" in text
    ):
        print(f"{gen_py} is already patched.")
        return 0

    if OLD not in text:
        print(
            f"Error: expected `match()` block not found in {gen_py}.\n"
            "  Likely cause: mlx-lm version drift. Inspect the file and update this script.",
            file=sys.stderr,
        )
        return 1

    gen_py.write_text(text.replace(OLD, NEW))
    print(f"Patched {gen_py}: match() now resets to initial state when s is None.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
