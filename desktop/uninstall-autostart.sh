#!/bin/zsh
# Undoes install-autostart.sh - Jarvis goes back to needing a manual double-click.
PLIST="$HOME/Library/LaunchAgents/com.jarvis.assistant.plist"
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
echo "Autostart removed. Jarvis won't launch automatically anymore."
