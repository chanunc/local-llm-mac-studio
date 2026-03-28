#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: deploy_mistral4_mlx_openai_server.sh [options]

Stage the local Mistral 4 MLA patch on the Mac Studio, verify version compatibility,
re-apply the patch, restart mlx-openai-server with the Mistral model, wait for
readiness, and run the smoke test.

Options:
  --host HOST                 SSH host alias (default: $MLX_MACSTUDIO_HOST or macstudio-ts)
  --port PORT                 Server port to bind/test (default: 8000)
  --wait-secs N               Seconds to wait for readiness (default: 120)
  --model-path PATH           Remote model path
  --served-model-name NAME    Served model name
  --force-unknown-version     Pass through to patch_mlx_openai_mistral4.py
  --skip-smoke-test           Restart the server but skip the smoke test
  -h, --help                  Show this help
EOF
}

log() {
  printf '[mistral4-deploy] %s\n' "$*"
}

HOST="${MLX_MACSTUDIO_HOST:-macstudio-ts}"
PORT="8000"
WAIT_SECS="120"
REMOTE_STAGE="/tmp/mistral4-patch"
REMOTE_PYTHON="~/mlx-openai-server-env/bin/python"
REMOTE_SERVER_BIN="~/mlx-openai-server-env/bin/mlx-openai-server"
REMOTE_LOG_PATH="/tmp/mlx-openai-server.log"
MODEL_PATH="~/.omlx/models/JANGQ-AI--Mistral-Small-4-119B-A6B-JANG_2L"
SERVED_MODEL_NAME="JANGQ-AI/Mistral-Small-4-119B-A6B-JANG_2L"
FORCE_UNKNOWN_VERSION=0
SKIP_SMOKE_TEST=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --wait-secs)
      WAIT_SECS="$2"
      shift 2
      ;;
    --model-path)
      MODEL_PATH="$2"
      shift 2
      ;;
    --served-model-name)
      SERVED_MODEL_NAME="$2"
      shift 2
      ;;
    --force-unknown-version)
      FORCE_UNKNOWN_VERSION=1
      shift
      ;;
    --skip-smoke-test)
      SKIP_SMOKE_TEST=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n\n' "$1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PATCH_SCRIPT="${REPO_ROOT}/scripts/patch_mlx_openai_mistral4.py"
SMOKE_SCRIPT="${REPO_ROOT}/scripts/smoke_test_mlx_openai_mistral4.py"
PATCH_MODULE="${REPO_ROOT}/patches/mlx_lm/mistral4.py"

for file in "$PATCH_SCRIPT" "$SMOKE_SCRIPT" "$PATCH_MODULE"; do
  if [[ ! -f "$file" ]]; then
    printf 'Required file not found: %s\n' "$file" >&2
    exit 1
  fi
done

SSH_OPTS=(-o BatchMode=yes)
SCP_OPTS=(-o BatchMode=yes)
PATCH_ARGS=()
if [[ "$FORCE_UNKNOWN_VERSION" == "1" ]]; then
  PATCH_ARGS+=(--force-unknown-version)
fi

ssh_remote() {
  ssh "${SSH_OPTS[@]}" "$HOST" "$@"
}

scp_remote() {
  scp "${SCP_OPTS[@]}" "$@"
}

log "Staging patch assets on ${HOST}"
ssh_remote "rm -rf \"$REMOTE_STAGE\" && mkdir -p \"$REMOTE_STAGE/scripts\" \"$REMOTE_STAGE/patches/mlx_lm\""
scp_remote "$PATCH_SCRIPT" "$HOST:$REMOTE_STAGE/scripts/"
scp_remote "$SMOKE_SCRIPT" "$HOST:$REMOTE_STAGE/scripts/"
scp_remote "$PATCH_MODULE" "$HOST:$REMOTE_STAGE/patches/mlx_lm/"

log "Checking remote package versions"
ssh_remote "cd \"$REMOTE_STAGE\" && $REMOTE_PYTHON scripts/patch_mlx_openai_mistral4.py --check-only --print-versions ${PATCH_ARGS[*]}"

log "Applying Mistral 4 patch"
ssh_remote "cd \"$REMOTE_STAGE\" && $REMOTE_PYTHON scripts/patch_mlx_openai_mistral4.py --print-versions ${PATCH_ARGS[*]}"

log "Restarting mlx-openai-server on ${HOST}"
ssh_remote "pkill -f mlx-openai-server || true; pkill -f run_mlx_openai_jang || true; sleep 2; JANG_PATCH_ENABLED=1 nohup $REMOTE_SERVER_BIN launch --model-path $MODEL_PATH --served-model-name '$SERVED_MODEL_NAME' --port $PORT --host 0.0.0.0 --no-log-file > $REMOTE_LOG_PATH 2>&1 &"

log "Waiting for port ${PORT} readiness"
READY=0
for ((i = 1; i <= WAIT_SECS; i++)); do
  if ssh_remote "curl -sf http://127.0.0.1:${PORT}/v1/models >/dev/null"; then
    READY=1
    break
  fi
  sleep 1
done

if [[ "$READY" != "1" ]]; then
  printf 'Server did not become ready within %s seconds.\n' "$WAIT_SECS" >&2
  ssh_remote "tail -n 40 $REMOTE_LOG_PATH" >&2 || true
  exit 1
fi

log "Server is responding on port ${PORT}"

if [[ "$SKIP_SMOKE_TEST" != "1" ]]; then
  log "Running smoke test"
  ssh_remote "JANG_PATCH_ENABLED=1 $REMOTE_PYTHON \"$REMOTE_STAGE/scripts/smoke_test_mlx_openai_mistral4.py\" --base-url http://127.0.0.1:${PORT} --model '$SERVED_MODEL_NAME' --model-path $MODEL_PATH"
else
  log "Skipping smoke test by request"
fi

log "Complete"
