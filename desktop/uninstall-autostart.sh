#!/bin/zsh
# Undoes install-autostart.sh - Jarvis goes back to needing a manual double-click.
AGENTS_DIR="$HOME/Library/LaunchAgents"
for label in com.jarvis.assistant com.jarvis.sentinel; do
  launchctl unload "$AGENTS_DIR/$label.plist" 2>/dev/null || true
  rm -f "$AGENTS_DIR/$label.plist"
done
echo "Autostart and standby listener removed."
