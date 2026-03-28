"""Smoke-test the local Mistral 4 MLA patch on mlx-openai-server.

Run this on the Mac Studio after patching and starting the server:
    JANG_PATCH_ENABLED=1 ~/mlx-openai-server-env/bin/python \
        scripts/smoke_test_mlx_openai_mistral4.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_MODEL = "JANGQ-AI/Mistral-Small-4-119B-A6B-JANG_2L"
DEFAULT_MODEL_PATH = str(
    Path.home() / ".omlx/models/JANGQ-AI--Mistral-Small-4-119B-A6B-JANG_2L"
)


class SmokeTestFailure(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--model-path", default=DEFAULT_MODEL_PATH)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--skip-direct",
        action="store_true",
        help="Skip the direct mlx_lm.generate validation step.",
    )
    return parser.parse_args()


def package_version(dist_name: str) -> str:
    try:
        return version(dist_name)
    except PackageNotFoundError:
        return "not installed"


def fetch_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: int,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for child in value.values():
            strings.extend(collect_strings(child))
        return strings
    if isinstance(value, list):
        strings: list[str] = []
        for child in value:
            strings.extend(collect_strings(child))
        return strings
    return []


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeTestFailure(message)


def run_direct_test(model_path: str) -> None:
    expect(
        os.environ.get("JANG_PATCH_ENABLED") == "1",
        "Direct test requires JANG_PATCH_ENABLED=1 in the environment.",
    )

    from mlx_lm import generate, load

    model, tokenizer = load(model_path)
    messages = [{"role": "user", "content": "Reply with exactly: hello from mistral"}]
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        reasoning_effort="none",
        enable_thinking=False,
    )
    text = generate(model, tokenizer, prompt=prompt, max_tokens=16, verbose=False)
    expect(
        "hello from mistral" in text.lower(),
        f"Direct generation returned unexpected text: {text!r}",
    )
    print(f"PASS direct mlx_lm.generate -> {text!r}")


def run_models_test(base_url: str, model: str, timeout: int) -> None:
    response = fetch_json("GET", f"{base_url}/v1/models", timeout=timeout)
    model_ids = [entry.get("id", "") for entry in response.get("data", [])]
    expect(model in model_ids, f"/v1/models did not include {model!r}: {model_ids!r}")
    print(f"PASS /v1/models -> {model}")


def run_chat_test(base_url: str, model: str, timeout: int) -> None:
    response = fetch_json(
        "POST",
        f"{base_url}/v1/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: hello from mistral"}],
            "max_tokens": 16,
        },
        timeout=timeout,
    )
    strings = " ".join(collect_strings(response)).lower()
    expect(
        "hello from mistral" in strings,
        f"/v1/chat/completions returned unexpected payload: {response!r}",
    )
    print("PASS /v1/chat/completions exact reply")


def run_reasoning_test(base_url: str, model: str, timeout: int) -> None:
    response = fetch_json(
        "POST",
        f"{base_url}/v1/chat/completions",
        payload={
            "model": model,
            "messages": [{"role": "user", "content": "What is 2+2? Answer in one word."}],
            "reasoning_effort": "high",
            "max_tokens": 16,
        },
        timeout=timeout,
    )
    strings = " ".join(collect_strings(response)).lower()
    expect(
        ("four" in strings) or (" 4" in strings) or strings.endswith("4"),
        f"Reasoning request returned unexpected payload: {response!r}",
    )
    print("PASS /v1/chat/completions reasoning_effort=high")


def run_responses_test(base_url: str, model: str, timeout: int) -> None:
    response = fetch_json(
        "POST",
        f"{base_url}/v1/responses",
        payload={
            "model": model,
            "input": "Reply with exactly: hello from mistral",
            "reasoning": {"effort": "none"},
            "max_output_tokens": 16,
        },
        timeout=timeout,
    )
    strings = " ".join(collect_strings(response)).lower()
    expect(
        "hello from mistral" in strings,
        f"/v1/responses returned unexpected payload: {response!r}",
    )
    print("PASS /v1/responses reasoning.effort=none")


def main() -> None:
    args = parse_args()
    print(f"mlx-lm: {package_version('mlx-lm')}")
    print(f"mlx-openai-server: {package_version('mlx-openai-server')}")
    print(f"base-url: {args.base_url}")
    print(f"model: {args.model}")

    if not args.skip_direct:
        run_direct_test(args.model_path)
    run_models_test(args.base_url, args.model, args.timeout)
    run_chat_test(args.base_url, args.model, args.timeout)
    run_reasoning_test(args.base_url, args.model, args.timeout)
    run_responses_test(args.base_url, args.model, args.timeout)
    print("All Mistral 4 MLA smoke tests passed.")


if __name__ == "__main__":
    try:
        main()
    except SmokeTestFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
