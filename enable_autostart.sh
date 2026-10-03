#!/bin/bash
# Enables J.A.R.V.I.S. to automatically open when your MacBook starts up or logs in

APP_PATH="/Applications/JARVIS.app"

echo "================================================="
echo "   Configuring J.A.R.V.I.S. macOS Autostart      "
echo "================================================="

# Add JARVIS.app to macOS Login Items
osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$APP_PATH\", hidden:false, name:\"JARVIS\"}" 2>/dev/null || true

echo "[✓] Autostart configured!"
echo "    J.A.R.V.I.S. will now open automatically"
echo "    every time you log into your MacBook."
echo ""
echo "    You can verify or toggle this at any time in:"
echo "    System Settings > General > Login Items"
echo "================================================="
