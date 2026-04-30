#!/usr/bin/env python3
"""Patch vllm-mlx streaming to parse tool calls when reasoning parser is active.

Bug: vllm-mlx's streaming path has two mutually exclusive branches:
  1. Reasoning parser path (--reasoning-parser) — extracts <think> but skips tool parsing
  2. Standard path — does tool parsing but no reasoning extraction

When both --reasoning-parser and --tool-call-parser are set, the reasoning
branch wins and tool calls leak into content as raw XML. The non-streaming path
runs them sequentially (tool parser first, reasoning parser second) and works fine.

Fix: In the reasoning parser branch, feed content through tool-call detection.
When <tool_call> markup is seen, buffer content instead of emitting it, then
parse using the generic parse_tool_calls() (which handles the Nemotron/XML
<function=name><parameter=p>v</parameter> format that Qwen3.5 MoE uses).

Also extends the end-of-stream fallback to cover accumulated_text from the
reasoning path and to fall back to parse_tool_calls() when the configured
parser fails.

Target: ~/vllm-mlx-env/lib/python3.12/site-packages/vllm_mlx/server.py
Idempotent. Backs up to server.py.bak.streaming-tools.

Usage:
    python3 scripts/patches/patch_vllm_mlx_streaming_tools.py
    # or from MacBook:
    ssh macstudio "~/vllm-mlx-env/bin/python ~/setup-llm-macstu/scripts/patches/patch_vllm_mlx_streaming_tools.py"
"""

import re
import shutil
import sys
from pathlib import Path

VENV = Path.home() / "vllm-mlx-env"
SERVER_PY = VENV / "lib" / "python3.12" / "site-packages" / "vllm_mlx" / "server.py"
BACKUP_SUFFIX = ".bak.streaming-tools"
PATCH_MARKER = "# PATCH: streaming-tools-reasoning-path"


def patch_server():
    if not SERVER_PY.exists():
        print(f"ERROR: {SERVER_PY} not found", file=sys.stderr)
        sys.exit(1)

    src = SERVER_PY.read_text()

    if PATCH_MARKER in src:
        print(f"Already patched (marker found). Skipping.")
        return

    # --- Patch 1: In the reasoning parser streaming branch, add tool-call buffering ---
    # Find the block where reasoning parser emits content/reasoning chunks,
    # and wrap the content emission with tool-call detection.

    # Original code (reasoning branch emit):
    old_reasoning_emit = """\
            if delta_msg is None:
                # Skip this chunk (e.g., <think> token itself)
                continue

            chunk = ChatCompletionChunk(
                id=response_id,
                model=_model_name,
                choices=[
                    ChatCompletionChunkChoice(
                        delta=ChatCompletionChunkDelta(
                            content=delta_msg.content,
                            reasoning=delta_msg.reasoning,
                        ),
                        finish_reason=output.finish_reason if output.finished else None,
                    )
                ],
                usage=get_usage(output) if output.finished else None,
            )
            yield f"data: {chunk.model_dump_json()}\\n\\n\""""

    new_reasoning_emit = f"""\
            if delta_msg is None:
                # Skip this chunk (e.g., <think> token itself)
                continue

            {PATCH_MARKER}
            # Feed content through tool-call detection when tool parser is active
            content_to_emit = delta_msg.content
            if tool_parser and content_to_emit:
                tool_accumulated_text += content_to_emit
                if not tool_markup_possible and "<" in content_to_emit:
                    tool_markup_possible = True
                if tool_markup_possible:
                    # Inside potential tool markup — suppress content emission
                    content_to_emit = None
                    if "</tool_call>" in tool_accumulated_text:
                        # Complete tool call — parse with generic parser (handles
                        # Nemotron XML format: <function=name><parameter=p>v</parameter>)
                        _, tc_list = parse_tool_calls(tool_accumulated_text)
                        if tc_list:
                            tool_calls_detected = True
                            tool_chunk = ChatCompletionChunk(
                                id=response_id,
                                model=_model_name,
                                choices=[
                                    ChatCompletionChunkChoice(
                                        delta=ChatCompletionChunkDelta(
                                            tool_calls=[
                                                {{
                                                    "index": i,
                                                    "id": tc.id,
                                                    "type": "function",
                                                    "function": {{
                                                        "name": tc.function.name,
                                                        "arguments": tc.function.arguments,
                                                    }},
                                                }}
                                                for i, tc in enumerate(tc_list)
                                            ]
                                        ),
                                        finish_reason="tool_calls" if output.finished else None,
                                    )
                                ],
                                usage=get_usage(output) if output.finished else None,
                            )
                            yield f"data: {{tool_chunk.model_dump_json()}}\\n\\n"
                            continue

            # Emit reasoning/content chunk (content may be suppressed if inside tool markup)
            if content_to_emit is not None or delta_msg.reasoning is not None:
                chunk = ChatCompletionChunk(
                    id=response_id,
                    model=_model_name,
                    choices=[
                        ChatCompletionChunkChoice(
                            delta=ChatCompletionChunkDelta(
                                content=content_to_emit,
                                reasoning=delta_msg.reasoning,
                            ),
                            finish_reason=(
                                "tool_calls" if (output.finished and tool_calls_detected)
                                else (output.finish_reason if output.finished else None)
                            ),
                        )
                    ],
                    usage=get_usage(output) if output.finished else None,
                )
                yield f"data: {{chunk.model_dump_json()}}\\n\\n\""""

    if old_reasoning_emit not in src:
        print("ERROR: Could not find reasoning emit block to patch.", file=sys.stderr)
        print("The server.py may have been updated. Manual patching needed.", file=sys.stderr)
        sys.exit(1)

    # --- Patch 2: Extend end-of-stream fallback to also try generic parse_tool_calls ---
    old_fallback = """\
    # Fallback: if tool parser accumulated text but never emitted tool_calls
    # (e.g., </tool_call> never arrived - incomplete tool call)
    if (
        tool_parser
        and tool_accumulated_text
        and not tool_calls_detected
        and "<tool_call>" in tool_accumulated_text
    ):
        result = tool_parser.extract_tool_calls(tool_accumulated_text)
        if result.tools_called:"""

    new_fallback = f"""\
    # Fallback: if tool parser accumulated text but never emitted tool_calls
    # (e.g., </tool_call> never arrived - incomplete tool call)
    {PATCH_MARKER}-fallback
    # Also check accumulated_text from reasoning path
    _fallback_text = tool_accumulated_text or ""
    if not _fallback_text and accumulated_text and "<tool_call>" in accumulated_text:
        _fallback_text = accumulated_text
    if (
        tool_parser
        and _fallback_text
        and not tool_calls_detected
        and "<tool_call>" in _fallback_text
    ):
        # Try configured parser first, then generic parse_tool_calls
        result = tool_parser.extract_tool_calls(_fallback_text)
        if not result.tools_called:
            _, _generic_tc = parse_tool_calls(_fallback_text)
            if _generic_tc:
                class _R:
                    tools_called = True
                    tool_calls = [{{"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments}} for tc in _generic_tc]
                result = _R()
        if result.tools_called:"""

    if old_fallback not in src:
        print("WARNING: Could not find fallback block. Applying patch 1 only.", file=sys.stderr)
        patched = src.replace(old_reasoning_emit, new_reasoning_emit)
    else:
        patched = src.replace(old_reasoning_emit, new_reasoning_emit)
        patched = patched.replace(old_fallback, new_fallback)

    # Backup
    backup = SERVER_PY.with_suffix(SERVER_PY.suffix + BACKUP_SUFFIX)
    if not backup.exists():
        shutil.copy2(SERVER_PY, backup)
        print(f"Backed up: {backup}")

    SERVER_PY.write_text(patched)
    print(f"Patched: {SERVER_PY}")
    print("Restart vllm-mlx to apply.")


if __name__ == "__main__":
    patch_server()
