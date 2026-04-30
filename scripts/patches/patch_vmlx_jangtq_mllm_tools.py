"""
Patch vmlx so the OpenAI `tools` array reaches the chat template on the
VLM/MLLM code path.

Why this exists
---------------
vmlx (1.0.3 inside MLX Studio v1.3.65 bundled Python) drops the OpenAI `tools`
array on the VLM/MLLM code path and mishandles tool-call replay. Tools reach
the qwen3 tool-call parser on the response side, but the prompt the model
sees never contains the tool descriptions or the qwen3 `<tool_call>` format
instructions. The model then emits `curl`/`fetch` as plain prose and OpenCode
renders it as text instead of executing a tool. Worse, on follow-up turns
where the client replays the prior assistant message with its `tool_calls`,
the Qwen3 chat template fails (`Can only get item pairs from a mapping`)
because `tool_calls[].function.arguments` is a JSON *string* (per the OpenAI
wire format) and the template expects a dict to iterate. vmlx falls back to
"last user message only", which drops the full tool/thinking context — the
model then thinks random nonsense unrelated to the task.

The bug spans three sites across two files:

  1. `vmlx_engine/engine/simple.py` — `SimpleEngine.chat()` and `.stream_chat()`
     extract `tools` as an explicit positional parameter, then forward
     `mllm_kwargs = dict(kwargs)` to `self._model.chat()` / `.stream_chat()`.
     Because `tools` was already pulled out of `kwargs`, `mllm_kwargs` never
     contains it. The MLLM model receives `**mllm_kwargs` with no tools.

  2. `vmlx_engine/models/mllm.py` — `MLLM.chat()` / `.stream_chat()` pop
     `enable_thinking` from kwargs but not `tools`. Even if upstream were
     fixed, `_apply_chat_template` ignores tools entirely. So the prompt is
     rendered without `tools=…`, and the model never sees them.

  3. `vmlx_engine/models/mllm.py` — `_apply_chat_template` never parses
     stringified `tool_calls[].function.arguments` into dicts before handing
     the messages to the Jinja chat template. The non-MLLM path in
     `simple.py` does this; the MLLM path forgets to. Result: multi-turn
     tool use fails with "Can only get item pairs from a mapping".

This affects every MLLM (`is_mllm=True`) model served via vmlx — most notably
`dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK` (the recommended uncensored default)
and the Qwen3.5-VL-122B CRACK family.

The text-only (non-MLLM) path is unaffected.

What this script does
---------------------
Applies these edits inside MLX Studio's bundled Python:

  - `vmlx_engine/engine/simple.py`
      * `SimpleEngine.chat()` MLLM branch: forward `template_tools` into
        `mllm_kwargs["tools"]`.
      * `SimpleEngine.stream_chat()` MLLM branch: same.
  - `vmlx_engine/models/mllm.py`
      * `MLLM._apply_chat_template(...)` accepts `tools=None` and pushes it
        into `template_kwargs["tools"]` when truthy.
      * `MLLM._apply_chat_template(...)` parses stringified
        `tool_calls[].function.arguments` into dicts before invoking the
        Jinja chat template (mirrors the non-MLLM branch in `simple.py`).
      * Both call sites of `_apply_chat_template` pop `tools` from kwargs and
        pass it through.

Idempotent — safe to re-run. Re-apply after every MLX Studio DMG upgrade
(the bundled-python tree is overwritten on install).

Usage
-----
    ssh macstudio "/Applications/vMLX.app/Contents/Resources/bundled-python/python/bin/python3 \\
        ~/setup-llm-macstu/scripts/patches/patch_vmlx_jangtq_mllm_tools.py"

Then restart vmlx with `--enable-auto-tool-choice --tool-call-parser qwen3`
(see CLAUDE.md vmlx switch snippet).

Upstream
--------
File a bug at https://github.com/jjang-ai/vmlx — the fix belongs in
`SimpleEngine.chat`/`stream_chat` (forward `tools`) and
`MLLM._apply_chat_template` (accept + forward `tools` to the template)
upstream so this patch can retire.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

BUNDLED_SITE = Path(
    "/Applications/vMLX.app/Contents/Resources/bundled-python/python/"
    "lib/python3.12/site-packages"
)
MLLM_PATH = BUNDLED_SITE / "vmlx_engine/models/mllm.py"
SIMPLE_PATH = BUNDLED_SITE / "vmlx_engine/engine/simple.py"


# ---------------------------------------------------------------------------
# mllm.py patches
# ---------------------------------------------------------------------------

MLLM_OLD_SIG = (
    "    def _apply_chat_template(\n"
    "        self,\n"
    "        chat_messages: list[dict],\n"
    "        enable_thinking: bool | None = None,\n"
    "    ) -> str:"
)
MLLM_NEW_SIG = (
    "    def _apply_chat_template(\n"
    "        self,\n"
    "        chat_messages: list[dict],\n"
    "        enable_thinking: bool | None = None,\n"
    "        tools: list | None = None,\n"
    "    ) -> str:"
)

MLLM_OLD_KWARGS = (
    "        template_kwargs = {}\n"
    "        if enable_thinking is not None:\n"
    "            template_kwargs[\"enable_thinking\"] = enable_thinking"
)
MLLM_NEW_KWARGS = (
    "        template_kwargs = {}\n"
    "        if enable_thinking is not None:\n"
    "            template_kwargs[\"enable_thinking\"] = enable_thinking\n"
    "        if tools:\n"
    "            template_kwargs[\"tools\"] = tools\n"
    "        for _m in chat_messages:\n"
    "            for _tc in _m.get(\"tool_calls\") or []:\n"
    "                _fn = _tc.get(\"function\", {})\n"
    "                _args = _fn.get(\"arguments\")\n"
    "                if isinstance(_args, str):\n"
    "                    try:\n"
    "                        import json as _json\n"
    "                        _fn[\"arguments\"] = _json.loads(_args)\n"
    "                    except Exception:\n"
    "                        _fn[\"arguments\"] = {}"
)

MLLM_OLD_CALL = (
    "        enable_thinking = kwargs.pop(\"enable_thinking\", None)\n"
    "        formatted_prompt = self._apply_chat_template(chat_messages, enable_thinking)"
)
MLLM_NEW_CALL = (
    "        enable_thinking = kwargs.pop(\"enable_thinking\", None)\n"
    "        _tools_for_tmpl = kwargs.pop(\"tools\", None)\n"
    "        formatted_prompt = self._apply_chat_template(chat_messages, enable_thinking, _tools_for_tmpl)"
)

MLLM_SENTINEL = "_tools_for_tmpl = kwargs.pop(\"tools\", None)"


# ---------------------------------------------------------------------------
# simple.py patches — two MLLM branches with different indentation
# ---------------------------------------------------------------------------

# chat(): MLLM branch is inside `async with self._generation_lock:` → 16-space indent
SIMPLE_OLD_CHAT = (
    "                mllm_kwargs = dict(kwargs)\n"
    "                if thinking_enabled is not None:\n"
    "                    mllm_kwargs[\"enable_thinking\"] = thinking_enabled\n"
    "                if reasoning_effort:\n"
    "                    mllm_kwargs[\"reasoning_effort\"] = reasoning_effort\n"
)
SIMPLE_NEW_CHAT = (
    "                mllm_kwargs = dict(kwargs)\n"
    "                if thinking_enabled is not None:\n"
    "                    mllm_kwargs[\"enable_thinking\"] = thinking_enabled\n"
    "                if reasoning_effort:\n"
    "                    mllm_kwargs[\"reasoning_effort\"] = reasoning_effort\n"
    "                if template_tools:\n"
    "                    mllm_kwargs[\"tools\"] = template_tools\n"
)

# stream_chat(): MLLM branch is NOT inside `async with` at that point → 12-space indent
SIMPLE_OLD_STREAM = (
    "            mllm_kwargs = dict(kwargs)\n"
    "            if thinking_enabled is not None:\n"
    "                mllm_kwargs[\"enable_thinking\"] = thinking_enabled\n"
    "            if reasoning_effort:\n"
    "                mllm_kwargs[\"reasoning_effort\"] = reasoning_effort\n"
)
SIMPLE_NEW_STREAM = (
    "            mllm_kwargs = dict(kwargs)\n"
    "            if thinking_enabled is not None:\n"
    "                mllm_kwargs[\"enable_thinking\"] = thinking_enabled\n"
    "            if reasoning_effort:\n"
    "                mllm_kwargs[\"reasoning_effort\"] = reasoning_effort\n"
    "            if template_tools:\n"
    "                mllm_kwargs[\"tools\"] = template_tools\n"
)

SIMPLE_SENTINEL_CHAT = "                    mllm_kwargs[\"tools\"] = template_tools"
SIMPLE_SENTINEL_STREAM = "                mllm_kwargs[\"tools\"] = template_tools"


def _patch_mllm() -> int:
    if not MLLM_PATH.exists():
        print(f"ERROR: {MLLM_PATH} does not exist.")
        return 1

    src = MLLM_PATH.read_text()

    already_patched = (
        MLLM_NEW_SIG in src
        and "template_kwargs[\"tools\"] = tools" in src
        and MLLM_SENTINEL in src
        and "_fn = _tc.get(\"function\", {})" in src
    )
    if already_patched:
        print(f"Already patched: {MLLM_PATH}")
        return 0

    backup = MLLM_PATH.with_suffix(".py.bak.tools")
    if not backup.exists():
        shutil.copy2(MLLM_PATH, backup)
        print(f"Backup written: {backup}")

    sig_count = src.count(MLLM_OLD_SIG)
    kw_count = src.count(MLLM_OLD_KWARGS)
    call_count = src.count(MLLM_OLD_CALL)
    if sig_count != 1 or kw_count != 1 or call_count != 2:
        print(
            "ERROR: vmlx mllm.py layout has changed. Found "
            f"signature={sig_count} (expected 1), "
            f"kwargs_init={kw_count} (expected 1), "
            f"call_sites={call_count} (expected 2). "
            "Inspect mllm.py manually and update this patch."
        )
        return 2

    src = src.replace(MLLM_OLD_SIG, MLLM_NEW_SIG)
    src = src.replace(MLLM_OLD_KWARGS, MLLM_NEW_KWARGS)
    src = src.replace(MLLM_OLD_CALL, MLLM_NEW_CALL)

    MLLM_PATH.write_text(src)
    print(f"Patched: {MLLM_PATH}")
    return 0


def _patch_simple() -> int:
    if not SIMPLE_PATH.exists():
        print(f"ERROR: {SIMPLE_PATH} does not exist.")
        return 1

    src = SIMPLE_PATH.read_text()

    already_patched = (
        SIMPLE_SENTINEL_CHAT in src
        and SIMPLE_SENTINEL_STREAM in src
    )
    if already_patched:
        print(f"Already patched: {SIMPLE_PATH}")
        return 0

    backup = SIMPLE_PATH.with_suffix(".py.bak.tools")
    if not backup.exists():
        shutil.copy2(SIMPLE_PATH, backup)
        print(f"Backup written: {backup}")

    chat_count = src.count(SIMPLE_OLD_CHAT)
    stream_count = src.count(SIMPLE_OLD_STREAM)
    if chat_count != 1 or stream_count != 1:
        print(
            "ERROR: vmlx simple.py layout has changed. Found "
            f"chat_branch={chat_count} (expected 1), "
            f"stream_branch={stream_count} (expected 1). "
            "Inspect simple.py manually and update this patch."
        )
        return 2

    src = src.replace(SIMPLE_OLD_CHAT, SIMPLE_NEW_CHAT)
    src = src.replace(SIMPLE_OLD_STREAM, SIMPLE_NEW_STREAM)

    SIMPLE_PATH.write_text(src)
    print(f"Patched: {SIMPLE_PATH}")
    return 0


def main() -> int:
    rc_mllm = _patch_mllm()
    rc_simple = _patch_simple()
    rc = rc_mllm or rc_simple
    if rc == 0:
        print("Restart vmlx for the change to take effect.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
