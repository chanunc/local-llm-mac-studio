#!/usr/bin/env python3
"""LLM-free port of the /list-model-to-remove skill.

Walks every Mac Studio model storage root over SSH, builds a single
deduplicated table (name · size · path · loaded-flag), and lets the operator
pick entries to delete. Mirrors the eight phases of
~/.claude/skills/list-model-to-remove/SKILL.md, but driven by argparse + stdin
prompts instead of an LLM.

The remote enumeration logic is reused verbatim from
~/.claude/skills/list-model-to-remove/inventory.sh (streamed over SSH).

Usage:
    python3 scripts/list_model_to_remove.py
    python3 scripts/list_model_to_remove.py --filter qwen3.5 --min-size 5
    python3 scripts/list_model_to_remove.py --root lmstudio
    python3 scripts/list_model_to_remove.py --host macstudio-ts
    python3 scripts/list_model_to_remove.py --dry-run
    python3 scripts/list_model_to_remove.py --filter <small-model> --yes

Behavior contract (do not diverge from these without updating SKILL.md too):
    - Loaded models flagged ● and refused-to-remove unless overridden.
    - Hard-link groups (same inode) collapse into one row; every path is
      deleted at execution so the disk space actually frees.
    - Per-root cleanup: hf → huggingface-cli delete-cache (rm -rf fallback);
      lmstudio → rm -rf <container-dir>; omlx → rm -rf <dir>;
      hauhau → rm <file>.
    - Mutates the Mac Studio filesystem only. Does not edit configs/, docs/,
      CLAUDE.md, or any submodule.

Exit codes:
    0  normal completion (incl. "no changes made" branches)
    1  no entries match the current filters
    2  SSH / connection error
    3  bad CLI argument
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

INVENTORY_SCRIPT = (
    Path.home() / ".claude" / "skills" / "list-model-to-remove" / "inventory.sh"
)

# Same regex as SKILL.md Phase 2.
LIVE_PROBE = (
    "ps -axo pid,command | grep -E "
    "'vllm-mlx|mlx-openai-server|mlx_lm\\.server|mlx_vlm\\.server|"
    "vmlx_engine|dflash-serve|lms server|llama-server|omlx' | grep -v grep; "
    "echo '---LMS-PS---'; "
    "~/.lmstudio/bin/lms ps --json 2>/dev/null"
)

ROOT_CHOICES = ("hf", "lmstudio", "omlx", "hauhau", "all")
GIB = 1024 ** 3


@dataclass
class Entry:
    root: str
    name: str
    size_bytes: int
    inode: int
    paths: list[str] = field(default_factory=list)
    loaded: bool = False


# ---------- SSH ----------

def ssh(host: str, remote_cmd: str, *, stdin: bytes | None = None) -> tuple[str, str, int]:
    """Run a single command on the Mac Studio. Returns (stdout, stderr, rc)."""
    proc = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=8", host, remote_cmd],
        input=stdin,
        capture_output=True,
        check=False,
    )
    return proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace"), proc.returncode


def ssh_stream_script(host: str, script_path: Path) -> tuple[str, str, int]:
    """Stream a local bash script over SSH via `bash -s`. Same as the skill driver."""
    with script_path.open("rb") as fh:
        proc = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8", host, "bash -s"],
            stdin=fh,
            capture_output=True,
            check=False,
        )
    return proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace"), proc.returncode


# ---------- Phases 2, 3 ----------

def liveness_probe(host: str) -> str:
    out, err, rc = ssh(host, LIVE_PROBE)
    if rc not in (0, 1):  # grep returns 1 when no matches; that's fine
        print(f"warning: liveness probe rc={rc}: {err.strip()}", file=sys.stderr)
    return out


def run_inventory(host: str) -> list[Entry]:
    if not INVENTORY_SCRIPT.exists():
        print(f"error: inventory script missing at {INVENTORY_SCRIPT}", file=sys.stderr)
        sys.exit(2)
    out, err, rc = ssh_stream_script(host, INVENTORY_SCRIPT)
    if rc != 0 and not out.strip():
        print(f"error: inventory ssh failed (rc={rc}): {err.strip()}", file=sys.stderr)
        sys.exit(2)
    if err.strip():
        # inventory.sh emits parse warnings to stderr; surface but don't abort.
        for line in err.splitlines():
            if line.strip():
                print(f"# inventory: {line}", file=sys.stderr)
    entries: list[Entry] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 4)
        if len(parts) != 5:
            continue
        root, name, size_s, inode_s, paths_s = parts
        try:
            size = int(size_s)
            inode = int(inode_s)
        except ValueError:
            continue
        paths = [p for p in paths_s.split("|") if p]
        entries.append(Entry(root=root, name=name, size_bytes=size, inode=inode, paths=paths))
    return entries


# ---------- Phase 3 transforms ----------

def apply_filters(entries: list[Entry], root: str, name_filter: str, min_bytes: int) -> list[Entry]:
    out = []
    for e in entries:
        if root != "all" and e.root != root:
            continue
        if name_filter and name_filter not in e.name.lower():
            continue
        if e.size_bytes < min_bytes:
            continue
        out.append(e)
    return out


def dedupe_by_inode(entries: list[Entry]) -> list[Entry]:
    """Merge rows with the same non-zero inode. Inode 0 is never merged."""
    by_inode: dict[int, Entry] = {}
    out: list[Entry] = []
    for e in entries:
        if e.inode == 0:
            out.append(e)
            continue
        if e.inode in by_inode:
            existing = by_inode[e.inode]
            for p in e.paths:
                if p not in existing.paths:
                    existing.paths.append(p)
        else:
            by_inode[e.inode] = e
            out.append(e)
    return out


def mark_loaded(entries: list[Entry], live_text: str) -> None:
    for e in entries:
        if e.name and e.name in live_text:
            e.loaded = True
            continue
        for p in e.paths:
            if p and p in live_text:
                e.loaded = True
                break


# ---------- Phase 4 ----------

def human_size(n: int) -> str:
    if n >= GIB:
        return f"{n / GIB:.1f} GiB"
    return f"{n / (1024 ** 2):.0f} MiB"


def fmt_path(p: str) -> str:
    home = os.path.expanduser("~")
    return p.replace(home, "~", 1) if p.startswith(home) else p


def render_table(entries: list[Entry], filtered_count: int) -> None:
    # Sort by size desc.
    entries.sort(key=lambda e: e.size_bytes, reverse=True)

    # Column widths.
    name_w = max(20, min(48, max((len(e.name) for e in entries), default=20)))
    server_w = max(8, max((len(e.root) for e in entries), default=8))

    header = f"{'#':>3}  {'Server':<{server_w}}  {'Model':<{name_w}}  {'Size':>10}  {'Loaded':<7}  Path(s)"
    print(header)
    print("-" * len(header))
    for i, e in enumerate(entries, 1):
        loaded = "●" if e.loaded else "-"
        primary = fmt_path(e.paths[0]) if e.paths else "(no path)"
        print(f"{i:>3}  {e.root:<{server_w}}  {e.name[:name_w]:<{name_w}}  {human_size(e.size_bytes):>10}  {loaded:<7}  {primary}")
        for extra in e.paths[1:]:
            pad = " " * (3 + 2 + server_w + 2 + name_w + 2 + 10 + 2 + 7 + 2)
            print(f"{pad}{fmt_path(extra)}")

    total_bytes = sum(e.size_bytes for e in entries)
    loaded_count = sum(1 for e in entries if e.loaded)
    print()
    print(f"Total: {len(entries)} models, {total_bytes / GIB:.1f} GiB on disk")
    print(f"Loaded (●): {loaded_count} model(s) — refused unless overridden")
    print(f"Filtered: {filtered_count} hidden by --filter / --min-size / --root")


# ---------- Phase 5 ----------

def parse_selection(reply: str, n_rows: int) -> tuple[str, list[int]]:
    """Returns (mode, indices). mode ∈ {'none','all','pick','bad'}.

    Indices are 1-based row numbers from the rendered table. Empty list for
    none/all (caller handles those modes specially).
    """
    s = reply.strip().lower()
    if s in ("", "none", "n", "abort", "q", "quit"):
        return ("none", [])
    if s == "all":
        return ("all", [])
    picks: list[int] = []
    for tok in s.replace(" ", "").split(","):
        if not tok:
            continue
        try:
            v = int(tok)
        except ValueError:
            return ("bad", [])
        if v < 1 or v > n_rows:
            return ("bad", [])
        if v not in picks:
            picks.append(v)
    if not picks:
        return ("bad", [])
    return ("pick", picks)


def prompt_selection(entries: list[Entry]) -> list[Entry]:
    """Phase 5. Returns the list of entries the user wants to remove (may be empty)."""
    while True:
        print()
        reply = input(
            "Reply with row numbers to remove (e.g. 3,7,12), 'all', or 'none' to abort: "
        )
        mode, picks = parse_selection(reply, len(entries))
        if mode == "bad":
            print("error: bad selection — use comma-separated row numbers in range, or 'all'/'none'")
            continue
        if mode == "none":
            return []
        if mode == "all":
            chosen = list(entries)
        else:
            chosen = [entries[i - 1] for i in picks]
        return chosen


def filter_loaded(chosen: list[Entry], assume_yes: bool) -> list[Entry]:
    """Phase 5 (loaded override). Default skip; --yes always skips."""
    out: list[Entry] = []
    for e in chosen:
        if not e.loaded:
            out.append(e)
            continue
        if assume_yes:
            print(f"  - skipping loaded entry '{e.name}' (--yes)")
            continue
        ans = input(f"  '{e.name}' is currently loaded. Skip? [Y/n]: ").strip().lower()
        if ans in ("", "y", "yes"):
            print(f"    skipped (loaded)")
        else:
            print(f"    KEPT — running server may crash on next inference")
            out.append(e)
    return out


# ---------- Phase 6 ----------

def cleanup_commands(e: Entry, hf_cli_available: bool) -> list[str]:
    """Per-root cleanup command(s). Returns the literal shell commands to run
    on the Mac Studio (without the leading 'ssh host'). Multiple paths in a
    hard-link group → multiple commands."""
    cmds: list[str] = []
    if e.root == "hf":
        if hf_cli_available:
            cmds.append(f"huggingface-cli delete-cache --disable-tui --repo {shquote(e.name)}")
        else:
            for p in e.paths:
                cmds.append(f"rm -rf {shquote(p)}")
    elif e.root == "lmstudio":
        for p in e.paths:
            target = os.path.dirname(p) if p.endswith(".gguf") else p
            cmds.append(f"rm -rf {shquote(target)}")
    elif e.root == "omlx":
        for p in e.paths:
            cmds.append(f"rm -rf {shquote(p)}")
    elif e.root == "hauhau":
        for p in e.paths:
            cmds.append(f"rm {shquote(p)}")
    return cmds


def shquote(s: str) -> str:
    """Single-quote a string for safe shell injection."""
    return "'" + s.replace("'", "'\\''") + "'"


def preview(chosen: list[Entry], hf_cli_available: bool) -> int:
    print()
    print(f"About to remove {len(chosen)} entries, freeing {sum(e.size_bytes for e in chosen)/GIB:.1f} GiB:")
    for e in chosen:
        print(f"  {e.root:<8}  {e.name:<40}  {human_size(e.size_bytes):>10}")
        for c in cleanup_commands(e, hf_cli_available):
            print(f"      {c}")
    return sum(e.size_bytes for e in chosen)


def confirm(assume_yes: bool) -> str:
    """Returns 'confirm', 'edit', or 'abort'."""
    if assume_yes:
        return "confirm"
    while True:
        ans = input("\nConfirm / Edit / Abort [C/e/a]: ").strip().lower()
        if ans in ("", "c", "confirm"):
            return "confirm"
        if ans in ("e", "edit"):
            return "edit"
        if ans in ("a", "abort"):
            return "abort"
        print("error: answer with C, e, or a")


# ---------- Phase 7 ----------

def probe_hf_cli(host: str) -> bool:
    out, _, _ = ssh(host, "command -v huggingface-cli >/dev/null 2>&1 && echo yes || echo no")
    return out.strip() == "yes"


def execute_removals(host: str, chosen: list[Entry], hf_cli_available: bool) -> tuple[int, list[str]]:
    """Returns (success_count, errors)."""
    successes = 0
    errors: list[str] = []
    for e in chosen:
        all_ok = True
        for cmd in cleanup_commands(e, hf_cli_available):
            print(f"  $ ssh {host} {cmd}")
            out, err, rc = ssh(host, cmd)
            if rc != 0:
                all_ok = False
                msg = (err or out).strip().splitlines()[-1] if (err or out).strip() else f"rc={rc}"
                errors.append(f"{e.root} {e.name} — {msg}")
                print(f"    ✗ {msg}")
            else:
                if out.strip():
                    print("    " + out.strip().splitlines()[-1])
        if all_ok:
            successes += 1
            print(f"  ✓ {e.name}")
    return successes, errors


# ---------- Phase 8 ----------

def verify(host: str, claimed_freed: int) -> None:
    out, _, _ = ssh(
        host,
        "du -sh ~/.cache/huggingface/hub ~/.lmstudio/models ~/.omlx/models ~/.cache/hauhau-gguf 2>/dev/null"
    )
    print()
    print("Disk usage after removal:")
    for line in out.splitlines():
        print(f"  {line}")
    print(f"Claimed freed: {claimed_freed/GIB:.1f} GiB (sum of selected entries' size_bytes)")
    print("If divergence vs reality is large, a hard-link is still held in another root.")


# ---------- main ----------

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--filter", default="", help="case-insensitive substring match against model name")
    ap.add_argument("--min-size", default="0", help="hide entries < N GiB (decimals ok)")
    ap.add_argument("--root", default="all", choices=ROOT_CHOICES, help="restrict enumeration to a single root")
    ap.add_argument("--host", default="macstudio", help="SSH alias for the Mac Studio (default: macstudio)")
    ap.add_argument("--dry-run", action="store_true", help="print table + exit; no prompts, no removals")
    ap.add_argument("--yes", action="store_true", help="non-interactive: auto-skip loaded entries, auto-confirm")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    try:
        min_gib = float(args.min_size)
    except ValueError:
        print("error: --min-size must be numeric (e.g. 5 or 5.5)", file=sys.stderr)
        return 3
    min_bytes = int(min_gib * GIB)

    name_filter = args.filter.lower()

    print(f"Probing {args.host} …")
    live_text = liveness_probe(args.host)
    raw_entries = run_inventory(args.host)
    if not raw_entries:
        print("inventory returned no rows — nothing to consider")
        return 1

    raw_count = len(raw_entries)
    filtered = apply_filters(raw_entries, args.root, name_filter, min_bytes)
    deduped = dedupe_by_inode(filtered)
    mark_loaded(deduped, live_text)
    hidden = raw_count - len(deduped)

    if not deduped:
        print("0 models match the current filters.")
        return 1

    while True:
        render_table(deduped, hidden)
        if args.dry_run:
            return 0

        chosen = prompt_selection(deduped)
        if not chosen:
            print("no changes made")
            return 0

        chosen = filter_loaded(chosen, args.yes)
        if not chosen:
            print("no changes made (every selection was loaded and skipped)")
            return 0

        hf_cli_available = probe_hf_cli(args.host)
        claimed = preview(chosen, hf_cli_available)
        decision = confirm(args.yes)
        if decision == "abort":
            print("aborted — no changes made")
            return 0
        if decision == "edit":
            continue
        # confirm
        successes, errors = execute_removals(args.host, chosen, hf_cli_available)
        verify(args.host, claimed)
        print()
        print(f"Removed {successes} of {len(chosen)} selected entries.")
        if errors:
            print(f"Errors: {len(errors)}")
            for line in errors:
                print(f"  ✗ {line}")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted — no changes made", file=sys.stderr)
        sys.exit(130)
