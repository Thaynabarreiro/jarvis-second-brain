#!/bin/zsh
# Double-click launcher (Mac): starts the system-wide Jarvis with the floating orb.
cd "$(dirname "$0")"
exec "$HOME/.jarvis/venv/bin/python" jarvis.py
