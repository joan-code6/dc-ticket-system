#!/bin/bash
# DC Ticket Bot — systemd user service manager
#   ./run.sh            Install, enable & start the service
#   ./run.sh start      Start the service
#   ./run.sh stop       Stop the service
#   ./run.sh restart    Restart the service
#   ./run.sh status     Show service status + recent logs
#   ./run.sh logs       Tail live logs
#   ./run.sh install    Create service + enable (don't start)
#   ./run.sh uninstall  Stop, disable & remove service

set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(pwd)"
SERVICE_NAME="dc-ticket-bot"
SERVICE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE_FILE="$SERVICE_DIR/$SERVICE_NAME.service"
LOGFILE="$ROOT/bot.log"

# ── helpers ──────────────────────────────────────────────

_setup_venv() {
    if [ ! -f "venv/bin/python3" ]; then
        echo "Creating venv..."
        python3 -m venv venv
        source venv/bin/activate
        pip install --upgrade pip -q
        pip install -r requirements.txt -q
        echo "venv ready."
        echo ""
    fi
}

_write_service() {
    mkdir -p "$SERVICE_DIR"
    cat > "$SERVICE_FILE" << SERVICEOF
[Unit]
Description=DC Ticket Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$ROOT/venv/bin/python3 -u bot/main.py
Restart=on-failure
RestartSec=10
StandardOutput=append:$LOGFILE
StandardError=append:$LOGFILE

[Install]
WantedBy=default.target
SERVICEOF
    echo "Service file written: $SERVICE_FILE"
}

_get_status() {
    if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo "active"
    elif systemctl --user is-failed --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo "failed"
    else
        echo "inactive"
    fi
}

_systemctl() {
    systemctl --user "$@"
}

# ── commands ─────────────────────────────────────────────

cmd_install() {
    _setup_venv
    if [ ! -f "$SERVICE_FILE" ]; then
        _write_service
    fi
    _systemctl daemon-reload
    _systemctl enable "$SERVICE_NAME"
    loginctl enable-linger "$USER" 2>/dev/null || true
    echo "Service installed and enabled."
    echo "Use './run.sh start' to start, './run.sh status' to check."
}

cmd_start() {
    if [ ! -f "$SERVICE_FILE" ]; then
        cmd_install
    fi
    _systemctl start "$SERVICE_NAME"
    echo "Started. Use './run.sh status' or './run.sh logs' to check."
}

cmd_stop() {
    _systemctl stop "$SERVICE_NAME"
    echo "Stopped."
}

cmd_restart() {
    _systemctl restart "$SERVICE_NAME"
    echo "Restarted."
}

cmd_status() {
    local state
    state=$(_get_status)
    echo "Service: $SERVICE_NAME"
    echo "Status:  $state"
    echo "Log:     $LOGFILE"
    echo "──────────────────────────────────────"
    _systemctl status "$SERVICE_NAME" --no-pager -l 2>/dev/null || true
    echo ""
    if [ -f "$LOGFILE" ]; then
        echo "── recent logs ────────────────────────"
        tail -20 "$LOGFILE"
    fi
}

cmd_logs() {
    if [ -f "$LOGFILE" ]; then
        echo "Tailing $LOGFILE (Ctrl+C to stop)..."
        tail -f "$LOGFILE"
    else
        echo "No log file yet. Start the bot first."
    fi
}

cmd_uninstall() {
    _systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    _systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "$SERVICE_FILE"
    _systemctl daemon-reload
    echo "Service removed."
}

# ── entrypoint ───────────────────────────────────────────

case "${1:-}" in
    install)   cmd_install ;;
    start)     cmd_start ;;
    stop)      cmd_stop ;;
    restart)   cmd_restart ;;
    status)    cmd_status ;;
    logs)      cmd_logs ;;
    uninstall) cmd_uninstall ;;
    *)         cmd_install && cmd_start ;;
esac
