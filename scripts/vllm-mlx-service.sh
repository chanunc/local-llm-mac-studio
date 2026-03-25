#!/bin/bash
# vllm-mlx service manager for Mac Studio
# Usage: vllm-service start|stop|restart|status|log
#
# Manages vllm-mlx as a launchd service, handling port 8000
# conflicts with oMLX automatically.

set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.chanunc.vllm-mlx.plist"
LABEL="com.chanunc.vllm-mlx"
LOG="/opt/homebrew/var/log/vllm-mlx.log"
BREW="/opt/homebrew/bin/brew"
PORT=8000

red()   { printf '\033[0;31m%s\033[0m\n' "$*"; }
green() { printf '\033[0;32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[0;33m%s\033[0m\n' "$*"; }

is_loaded() {
    launchctl list "$LABEL" &>/dev/null
}

is_port_open() {
    lsof -i :"$PORT" -sTCP:LISTEN &>/dev/null
}

port_owner() {
    lsof -i :"$PORT" -sTCP:LISTEN 2>/dev/null | awk 'NR==2{print $1}'
}

stop_omlx() {
    if "$BREW" services list 2>/dev/null | grep -q "omlx.*started"; then
        yellow "Stopping oMLX (owns port $PORT)..."
        "$BREW" services stop omlx
        sleep 2
    fi
    # Kill any remaining omlx processes on the port
    if is_port_open; then
        local owner
        owner=$(port_owner)
        if [[ "$owner" == "Python" ]] || [[ "$owner" == "omlx" ]]; then
            yellow "Force-killing process on port $PORT..."
            lsof -ti :"$PORT" -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
            sleep 2
        fi
    fi
}

start_omlx() {
    yellow "Restarting oMLX..."
    "$BREW" services start omlx
}

cmd_start() {
    if is_loaded; then
        yellow "vllm-mlx is already running."
        cmd_status
        return
    fi

    if ! [[ -f "$PLIST" ]]; then
        red "Plist not found: $PLIST"
        echo "Copy it from the repo: scp configs/vllm-mlx.plist macstudio:~/Library/LaunchAgents/com.chanunc.vllm-mlx.plist"
        exit 1
    fi

    stop_omlx

    if is_port_open; then
        red "Port $PORT still in use by: $(port_owner)"
        echo "Kill the process manually: lsof -ti :$PORT | xargs kill -9"
        exit 1
    fi

    green "Starting vllm-mlx..."
    launchctl load "$PLIST"
    sleep 5

    if is_loaded; then
        green "vllm-mlx started."
        cmd_status
    else
        red "Failed to start. Check log: $LOG"
        tail -20 "$LOG" 2>/dev/null
        exit 1
    fi
}

cmd_stop() {
    if ! is_loaded; then
        yellow "vllm-mlx is not running."
        return
    fi

    green "Stopping vllm-mlx..."
    launchctl unload "$PLIST"
    sleep 2

    # Kill any leftover processes
    if is_port_open; then
        lsof -ti :"$PORT" -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
        sleep 1
    fi

    green "vllm-mlx stopped."
    start_omlx
}

cmd_restart() {
    if is_loaded; then
        launchctl unload "$PLIST"
        sleep 2
        if is_port_open; then
            lsof -ti :"$PORT" -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
            sleep 1
        fi
    fi

    green "Restarting vllm-mlx..."
    launchctl load "$PLIST"
    sleep 5
    cmd_status
}

cmd_status() {
    echo "=== vllm-mlx service ==="
    if is_loaded; then
        local pid
        pid=$(launchctl list "$LABEL" 2>/dev/null | awk '/PID/{print $NF}' || true)
        if [[ -z "$pid" ]]; then
            pid=$(launchctl list | grep "$LABEL" | awk '{print $1}')
        fi
        green "  State:  running (PID: $pid)"
    else
        red "  State:  stopped"
    fi

    if is_port_open; then
        local owner
        owner=$(port_owner)
        green "  Port:   $PORT ($owner)"
    else
        yellow "  Port:   $PORT (not listening)"
    fi

    # Health check
    if is_port_open; then
        local models
        models=$(curl -s --connect-timeout 2 "http://localhost:$PORT/v1/models" 2>/dev/null || echo "")
        if [[ -n "$models" ]] && echo "$models" | python3 -c 'import sys,json; json.load(sys.stdin)' 2>/dev/null; then
            green "  Health: OK"
            echo "$models" | python3 -c 'import sys,json; [print(f"  Model:  {m[\"id\"]}") for m in json.load(sys.stdin).get("data",[])]' 2>/dev/null || true
        else
            yellow "  Health: starting up..."
        fi
    fi

    echo "  Log:    $LOG"
}

cmd_log() {
    if [[ -f "$LOG" ]]; then
        tail -f "$LOG"
    else
        red "No log file: $LOG"
        exit 1
    fi
}

cmd_swap() {
    cmd_stop
}

case "${1:-help}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    restart) cmd_restart ;;
    status)  cmd_status ;;
    log)     cmd_log ;;
    swap)    cmd_swap ;;
    *)
        echo "Usage: vllm-service {start|stop|restart|status|log|swap}"
        echo ""
        echo "  start    Stop oMLX, start vllm-mlx"
        echo "  stop     Stop vllm-mlx, restart oMLX"
        echo "  restart  Restart vllm-mlx (no oMLX swap)"
        echo "  status   Show service state and health"
        echo "  log      Tail the log file"
        echo "  swap     Switch back to oMLX (alias for stop)"
        exit 1
        ;;
esac
