# OpenClaw Known Issues

## `mlx-openai-server` warning: ignored `store` field

When OpenClaw calls `mlx-openai-server`, the server may log:

```text
WARNING | app.schemas.openai:__log_extra_fields__ | The following fields were present in the request but ignored: {'store'}
```

### What it means

OpenClaw is sending an extra OpenAI-style request field named `store`.

`mlx-openai-server` accepts extra fields for compatibility, but it logs any fields that are not implemented in its local request schema. The request still succeeds.

This is **not**:
- a model error
- a Qwen3-Coder-Next issue
- a tool-calling failure
- an API mode mismatch

It is a harmless compatibility warning.

### What `store` means

`store` is a persistence hint used by newer OpenAI-style clients and APIs.

In OpenAI-hosted APIs, `store` controls whether the provider retains response state for later retrieval or follow-up workflows. It is about server-side persistence, not generation behavior.

It is **not**:
- prompt caching
- KV cache storage
- training on your data
- a sampling or reasoning setting

### Why it appears here

OpenClaw sends `store`, but the current `mlx-openai-server` chat-completions schema does not define that field.

As a result:
- the field is ignored
- the request continues normally
- the server logs a warning for visibility

### Impact

No functional impact is expected for normal local use.

If the model response is otherwise correct, you can safely ignore this warning.

### Optional fixes

If you want to silence the warning:

1. Change OpenClaw so it does not send `store`, if OpenClaw exposes a setting for that.
2. Patch `mlx-openai-server` to accept `store` silently in its request schema.
