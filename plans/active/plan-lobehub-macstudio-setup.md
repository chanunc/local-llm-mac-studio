# Plan: Wire self-hosted LobeHub to Mac Studio (vllm-mlx + vmlx)

## Context

You have a self-hosted LobeHub (Docker) instance but it isn't pointed at the Mac Studio, so no local models are reachable. The two servers currently running on Mac Studio are **vllm-mlx** (primary, Qwen3.5 JANG models) and **vmlx** (JANGTQ-CRACK models). Both speak OpenAI- and Anthropic-compatible APIs on `:8000` but are **mutually exclusive** — only one runs at a time on that port.

Goal: add LobeHub to the repo's existing per-server / per-client config pattern so the setup is (1) actually working today and (2) persisted in this repo alongside the OpenCode / Claude Code / Qwen Code configs. Since LobeHub is Docker-hosted, env vars are the primary config mechanism.

Key LobeHub facts driving the design (sourced from lobehub.com/docs):
- OpenAI-compatible slot: `OPENAI_PROXY_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL_LIST`. Base URL must include `/v1`.
- Native Anthropic slot: `ANTHROPIC_PROXY_URL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL_LIST`. Base URL is the server root (no `/v1`).
- `*_MODEL_LIST` syntax: `-all,+model-id=Display Name<ctx:fc:reasoning:vision:...>` ([docs](https://lobehub.com/docs/self-hosting/advanced/model-list)).
- One Docker instance has one canonical OpenAI slot and one canonical Anthropic slot; extra custom providers can only be added post-boot via the UI ([issue #12288](https://github.com/lobehub/lobehub/issues/12288)). That matches your layout fine because vllm-mlx and vmlx share port 8000 and you swap between them.

## Approach

Swap-an-env-file model: one `lobehub.env` per server, sourced at `docker run` time. When you flip the Mac Studio server (per CLAUDE.md "Switch to ..." commands), you also swap which env file LobeHub boots with. Both files use the same `:8000` base URL; only the model IDs differ.

Expose both API flavors per server — `OPENAI_*` and `ANTHROPIC_*` — because the Mac Studio servers speak both natively. LobeHub users can pick either depending on whether they want tool-call parity with Claude-style clients or plain OpenAI chat.

## Files to create / modify

### New env files (primary deliverable)

**`configs/client/vllm-mlx/lobehub.env`** — two slots, both pointed at vllm-mlx:
```env
OPENAI_API_KEY=not-needed
OPENAI_PROXY_URL=http://<MAC_STUDIO_IP>:8000/v1
OPENAI_MODEL_LIST=-all,+JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S=Qwen3.5-122B JANG 2S<200000:fc:reasoning>,+JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K=Qwen3.5-35B JANG 4K<262144:fc:reasoning>

ANTHROPIC_API_KEY=not-needed
ANTHROPIC_PROXY_URL=http://<MAC_STUDIO_IP>:8000
ANTHROPIC_MODEL_LIST=-all,+JANGQ-AI/Qwen3.5-122B-A10B-JANG_2S=Qwen3.5-122B JANG 2S<200000:fc:reasoning>,+JANGQ-AI/Qwen3.5-35B-A3B-JANG_4K=Qwen3.5-35B JANG 4K<262144:fc:reasoning>
```
Context/capability numbers mirror `configs/client/vllm-mlx/opencode.json` so limits stay in one place conceptually.

**`configs/client/vmlx/lobehub.env`** — same shape, vmlx's three JANGTQ-CRACK models:
```env
OPENAI_API_KEY=not-needed
OPENAI_PROXY_URL=http://<MAC_STUDIO_IP>:8000/v1
OPENAI_MODEL_LIST=-all,+dealignai/MiniMax-M2.7-JANGTQ-CRACK=MiniMax-M2.7 JANGTQ-CRACK<131072:fc:reasoning>,+dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK=Qwen3.6-35B JANGTQ4-CRACK<262144:fc:reasoning>,+dealignai/Qwen3.6-35B-A3B-JANGTQ2-CRACK=Qwen3.6-35B JANGTQ2-CRACK<262144:fc>

ANTHROPIC_API_KEY=not-needed
ANTHROPIC_PROXY_URL=http://<MAC_STUDIO_IP>:8000
ANTHROPIC_MODEL_LIST=-all,+dealignai/MiniMax-M2.7-JANGTQ-CRACK=MiniMax-M2.7 JANGTQ-CRACK<131072:fc:reasoning>,+dealignai/Qwen3.6-35B-A3B-JANGTQ4-CRACK=Qwen3.6-35B JANGTQ4-CRACK<262144:fc:reasoning>,+dealignai/Qwen3.6-35B-A3B-JANGTQ2-CRACK=Qwen3.6-35B JANGTQ2-CRACK<262144:fc>
```
Capability flags (`fc`, `reasoning`) lifted directly from `configs/client/vmlx/opencode.json`; JANGTQ2-CRACK drops `reasoning` because that config marks it `tools` only.

### New setup doc

**`docs/clients/lobehub-setup.md`** — follow the style of `docs/clients/opencode-setup.md` and `qwen-code-setup.md`. Sections:

1. **Prerequisites** — Docker installed locally; Mac Studio reachable at `<MAC_STUDIO_IP>` over LAN or `macstudio-ts.tailnet` over Tailscale; one of vllm-mlx or vmlx currently running (link to CLAUDE.md Switch commands).
2. **Fill placeholders** — `sed -i '' 's/<MAC_STUDIO_IP>/192.168.x.y/' configs/client/vllm-mlx/lobehub.env` (and the vmlx one). Note that `not-needed` is LobeHub-required non-empty; vllm-mlx / vmlx ignore auth.
3. **Docker run example** — `docker run -d --name lobe --env-file configs/client/vllm-mlx/lobehub.env -p 3210:3210 lobehub/lobe-chat`. For persistence / auth-enabled db mode, link to `lobehub/lobe-chat-database` image and the `lobehub/lobe-chat-compose` repo.
4. **Switching servers** — `docker stop lobe && docker rm lobe && docker run ... --env-file configs/client/vmlx/lobehub.env ...` after switching the Mac Studio server. Or mount both env files and symlink `active.env` — mention briefly.
5. **UI verification** — open `http://localhost:3210`, go to `Settings → AI Service Provider → OpenAI`, click "Get Model List". Registered JANG / CRACK IDs should populate. Same flow for Anthropic tab.
6. **Adding a second concurrent provider via UI** — click "Add Custom Provider" post-boot if you ever run two Mac Studio endpoints on different ports (future-proof note; not needed today since vllm-mlx and vmlx share port 8000).
7. **Troubleshooting** — empty responses usually mean missing `/v1` on OpenAI base URL ([LobeHub docs](https://lobehub.com/docs/usage/providers/openai)); model not in list usually means `-all` without a matching `+id`; tool calls failing on vllm-mlx → confirm server started with `--tool-call-parser qwen3_coder` (see CLAUDE.md).

### README / docs cross-references

- **`README.md`** — find the "Coding Agents" / clients table (per explore: agents + description + link column) and add a **LobeHub** row. Since LobeHub is a chat UI rather than a coding agent, insert it in a "Chat UIs" subsection underneath, or relabel the existing table to "Clients" if it already covers Claude Code and OpenCode. Link target: `docs/clients/lobehub-setup.md`.
- **`configs/README.md`** — in the per-server "Config Files" subsections for vllm-mlx and vmlx, add `lobehub.env → (sourced at docker run time)` alongside the existing rows.

## Critical files to read / match during implementation

- `configs/client/vllm-mlx/opencode.json`, `configs/client/vmlx/opencode.json` — canonical model IDs, context limits, capability flags. LobeHub env strings must stay consistent with these.
- `docs/clients/opencode-setup.md`, `docs/clients/qwen-code-setup.md` — tone and section layout for the new setup doc.
- `README.md`, `configs/README.md` — structure of the clients / config-files tables so the LobeHub additions slot in cleanly.
- `CLAUDE.md` "Editing Workflow" — LobeHub env files for vllm-mlx and vmlx do NOT need to be kept in sync across all 4 server folders (per the rule that vllm-mlx configs and vmlx configs are independent). Only vllm-mlx and vmlx get a `lobehub.env`.

## Explicit non-goals

- No env files for mlx-openai-server or oMLX this pass — per your scope answer. Easy to add later by copying the pattern.
- Not building a `docker-compose.yml` — user can already run LobeHub; the setup doc only shows the `docker run` one-liner plus pointers to the official compose repo.
- Not modifying any Mac Studio side settings (`~/.omlx/model_settings.json`, start scripts, etc.) — purely a client-side wiring change.
- No real IPs / API keys in committed files — preserve `<MAC_STUDIO_IP>` / `not-needed` placeholder conventions.

## Verification

After implementation:

1. **Placeholder lint** — `grep -R "<MAC_STUDIO_IP>" configs/client/vllm-mlx/lobehub.env configs/client/vmlx/lobehub.env` should show the placeholder (confirming no accidental leak of real IP).
2. **Env file syntax** — `docker run --rm --env-file configs/client/vllm-mlx/lobehub.env alpine env | grep -E '^(OPENAI|ANTHROPIC)_'` to confirm all 6 vars parse.
3. **End-to-end (user-run)** — with the real IP filled in and vllm-mlx running on Mac Studio: `docker run -d --name lobe --env-file … -p 3210:3210 lobehub/lobe-chat`, open `http://localhost:3210`, Settings → OpenAI → Get Model List → expect the two JANG IDs to populate. Send a message to `Qwen3.5-35B JANG 4K`. Swap env files + restart container and repeat for vmlx with `Qwen3.6-35B JANGTQ4-CRACK`.
4. **Doc cross-link check** — README link to `docs/clients/lobehub-setup.md` resolves; `configs/README.md` mentions both new env files.
