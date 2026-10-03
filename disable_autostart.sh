#!/bin/bash
# Removes Jarvis from macOS Login Items
osascript -e 'tell application "System Events" to delete login item "Jarvis"' 2>/dev/null || true
echo "[✓] Jarvis removed from macOS Login Items."
