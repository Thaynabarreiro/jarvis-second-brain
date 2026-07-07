#!/bin/zsh
# Makes Jarvis start automatically at login, AND brings it back with "Hey
# Jarvis"/two claps any time you fully quit it - you never touch a launcher
# file again. Uses two macOS LaunchAgents:
#   com.jarvis.assistant - the full app, started once at login
#   com.jarvis.sentinel   - a tiny standby listener (KeepAlive) that relaunches
#                           the full app on a wake trigger whenever it's closed
set -e
DESKTOP_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$AGENTS_DIR"

cat > "$AGENTS_DIR/com.jarvis.assistant.plist" << PLIST_EOF
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

cat > "$AGENTS_DIR/com.jarvis.sentinel.plist" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jarvis.sentinel</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/.jarvis/venv/bin/python</string>
        <string>$DESKTOP_DIR/wake_sentinel.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$DESKTOP_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/.jarvis/sentinel.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.jarvis/sentinel.log</string>
</dict>
</plist>
PLIST_EOF

for label in com.jarvis.assistant com.jarvis.sentinel; do
  launchctl unload "$AGENTS_DIR/$label.plist" 2>/dev/null || true
  launchctl load "$AGENTS_DIR/$label.plist"
done

echo "Done. Jarvis starts automatically at login, and 'Hey Jarvis' or two claps"
echo "bring it back any time you fully quit it - no launcher file needed again."
echo "To undo this later, run: ./uninstall-autostart.sh"
