#!/bin/bash
# Discord Ticket Bot - Runner (Linux/macOS)
#   ./run.sh          Foreground session with auto-reload
#   ./run.sh daemon   Start as background daemon (nohup)
#   ./run.sh status   Show daemon status and latest logs
#   ./run.sh stop     Stop the daemon

set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PIDFILE="bot.pid"
LOGFILE="bot.log"

# ── helpers ──────────────────────────────────────────────

_load_env() {
    if [ -f ".env" ]; then
        export $(grep -v '^\s*#' .env | grep -v '^\s*$' | xargs) || true
    fi
    if [ -n "${DC_TOKEN:-}" ]; then
        export DISCORD_BOT_TOKEN="$DC_TOKEN"
    fi
}

_setup_venv() {
    if [ ! -f "venv/bin/python3" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip -q
        pip install -r requirements.txt -q
        echo "venv ready."
        echo ""
    fi
}

_get_python() {
    if [ -f "venv/bin/python3" ]; then
        echo "venv/bin/python3"
    elif command -v python3 &>/dev/null; then
        command -v python3
    elif command -v python &>/dev/null; then
        command -v python
    else
        echo "Error: Python not found." >&2
        exit 1
    fi
}

_daemon_running() {
    if [ -f "$PIDFILE" ]; then
        local pid
        pid=$(cat "$PIDFILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# ── status ───────────────────────────────────────────────

cmd_status() {
    if _daemon_running; then
        local pid
        pid=$(cat "$PIDFILE")
        echo "Bot daemon is RUNNING (PID: $pid)"
        echo "──────────────────────────────────────"
        if [ -f "$LOGFILE" ]; then
            tail -20 "$LOGFILE"
        fi
    else
        echo "Bot daemon is NOT running."
        if [ -f "$LOGFILE" ]; then
            echo ""
            echo "Last logs:"
            echo "──────────────────────────────────────"
            tail -10 "$LOGFILE"
        fi
    fi
}

# ── stop ─────────────────────────────────────────────────

cmd_stop() {
    if _daemon_running; then
        local pid
        pid=$(cat "$PIDFILE")
        echo "Stopping bot daemon (PID: $pid)..."
        kill "$pid" 2>/dev/null || true
        sleep 2
        if kill -0 "$pid" 2>/dev/null; then
            echo "Force killing..."
            kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$PIDFILE"
        echo "Stopped."
    else
        echo "No daemon running."
    fi
}

# ── daemon ───────────────────────────────────────────────

cmd_daemon() {
    if _daemon_running; then
        echo "Bot daemon is already running (PID: $(cat "$PIDFILE"))."
        echo "Use './run.sh status' to view logs or './run.sh stop' to stop."
        exit 0
    fi

    _load_env
    if [ -z "${DISCORD_BOT_TOKEN:-}" ]; then
        echo "Error: DISCORD_BOT_TOKEN is not set. Add DC_TOKEN to .env."
        exit 1
    fi

    _setup_venv
    PYTHON=$(_get_python)

    echo "Starting bot daemon..."
    nohup "$PYTHON" -u bot/main.py >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    echo "Bot daemon started (PID: $(cat "$PIDFILE"))."
    echo ""

    # Show logs as they come in for a few seconds
    echo "──────────────────────────────────────"
    echo "Latest logs (Ctrl+C to stop watching, bot keeps running):"
    echo ""
    tail -f "$LOGFILE" 2>/dev/null || true
}

# ── foreground (default) ─────────────────────────────────

cmd_run() {
    _load_env
    if [ -z "${DISCORD_BOT_TOKEN:-}" ]; then
        echo "Error: DISCORD_BOT_TOKEN is not set. Add DC_TOKEN to .env."
        exit 1
    fi

    _setup_venv
    PYTHON=$(_get_python)

    echo "Starting bot with auto-reload on file changes..."
    echo "Watching: bot/**/*.py"
    echo ""

    MARKER=$(mktemp /tmp/ticket-bot-marker.XXXXXX)
    trap 'rm -f "$MARKER"' EXIT SIGINT SIGTERM

    while true; do
        _load_env
        if [ -z "${DISCORD_BOT_TOKEN:-}" ]; then
            echo "Error: DISCORD_BOT_TOKEN missing. Exiting."
            exit 1
        fi

        echo "[run] Starting bot..."
        touch "$MARKER"
        "$PYTHON" -u bot/main.py &
        BOT_PID=$!
        echo "[run] Bot started (PID: $BOT_PID)"

        while true; do
            sleep 2

            if ! kill -0 $BOT_PID 2>/dev/null; then
                wait $BOT_PID 2>/dev/null
                echo "[run] Bot exited with code $?."
                break
            fi

            CHANGED=$(find bot/ \
                -name '*.py' \
                -newer "$MARKER" \
                -not -path '*/__pycache__/*' \
                -print -quit 2>/dev/null)

            if [ -n "$CHANGED" ]; then
                echo "[run] Change detected: $CHANGED"
                kill $BOT_PID 2>/dev/null || true
                wait $BOT_PID 2>/dev/null || true
                break
            fi

            touch "$MARKER"
        done

        sleep 1
    done
}

# ── entrypoint ───────────────────────────────────────────

case "${1:-}" in
    daemon)  cmd_daemon ;;
    status)  cmd_status ;;
    stop)    cmd_stop ;;
    *)       cmd_run ;;
esac
