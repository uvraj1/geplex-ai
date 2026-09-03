#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/geplex-ui.service"

if [ ! -f "$SERVICE_FILE" ]; then
  echo "Error: geplex-ui.service not found in $SCRIPT_DIR"
  exit 1
fi

echo "Installing GepLex UI service..."
echo "Make sure you've edited geplex-ui.service with your username and paths first!"
echo ""

sudo cp "$SERVICE_FILE" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable geplex-ui
sudo systemctl start geplex-ui
sudo systemctl status geplex-ui
