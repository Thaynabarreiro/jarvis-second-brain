#!/bin/zsh
# Double-click launcher (Mac): stops the running Jarvis daemon, if any.
PIDFILE="$HOME/.jarvis/jarvis.pid"
if [ -f "$PIDFILE" ]; then
  PID=$(cat "$PIDFILE")
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    echo "Jarvis stopped (pid $PID)."
  else
    echo "Jarvis wasn't running."
  fi
  rm -f "$PIDFILE"
else
  echo "Jarvis wasn't running."
fi
sleep 2
