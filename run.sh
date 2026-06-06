#!/bin/bash
# Discord Ticket Bot - Development Runner (Linux/macOS)
# Restarts the bot automatically when Python/JSON files change in bot/

set -euo pipefail
cd "$(dirname "$0")"

# Load token from .env
if [ -f ".env" ]; then
    export $(grep -v '^\s*#' .env | grep -v '^\s*$' | xargs)
fi
if [ -n "${DC_TOKEN:-}" ] && [ -z "${DISCORD_BOT_TOKEN:-}" ]; then
    export DISCORD_BOT_TOKEN="$DC_TOKEN"
fi

if [ -z "${DISCORD_BOT_TOKEN:-}" ]; then
    echo "Error: DISCORD_BOT_TOKEN is not set. Add DC_TOKEN to .env or set DISCORD_BOT_TOKEN."
    exit 1
fi

if ! command -v python &>/dev/null && ! command -v python3 &>/dev/null; then
    echo "Error: Python is not installed or not in PATH."
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)

echo "Starting bot with auto-reload on file changes..."
echo "Watching: bot/**/*.py"
echo ""

# Marker file tracks the last known state for change detection
MARKER=$(mktemp /tmp/ticket-bot-marker.XXXXXX)
trap 'rm -f "$MARKER"' EXIT SIGINT SIGTERM

while true; do
    touch "$MARKER"
    $PYTHON -u bot/main.py &
    BOT_PID=$!
    echo "[run] Bot started (PID: $BOT_PID)"

    while true; do
        sleep 2

        if ! kill -0 $BOT_PID 2>/dev/null; then
            echo "[run] Bot process exited."
            break
        fi

        CHANGED=$(find bot/ \
            -name '*.py' \
            -newer "$MARKER" \
            -not -path '*/__pycache__/*' \
            -not -name '.run_ref' \
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
