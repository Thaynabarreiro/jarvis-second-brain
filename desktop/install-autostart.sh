#!/bin/zsh
# Makes Jarvis start automatically whenever you log into this Mac, so you
# never have to double-click Jarvis-Desktop.command again. Uses a macOS
# LaunchAgent (the standard, reliable way to auto-start an app at login).
set -e
DESKTOP_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.jarvis.assistant.plist"

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jarvis.assistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/.jarvis/venv/bin/python</string>
        <string>$DESKTOP_DIR/jarvis.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$DESKTOP_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/.jarvis/jarvis.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.jarvis/jarvis.log</string>
</dict>
</plist>
PLIST_EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "Done. Jarvis will now start automatically every time you log in."
echo "It's starting right now too - give it ~15 seconds for the orb to appear."
echo "To undo this later, run: ./uninstall-autostart.sh"
