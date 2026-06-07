#!/bin/bash
# Discord Ticket Bot - Deploy Script (Linux/macOS)
# Creates a venv and installs dependencies

set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is not installed or not in PATH."
    exit 1
fi

echo "Creating virtual environment..."
python3 -m venv venv

echo "Activating venv and installing packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Deploy complete. Start the bot with:"
echo "  source venv/bin/activate && python bot/main.py"
echo "Or use the auto-reload runner:"
echo "  ./run.sh"
