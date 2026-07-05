#!/bin/zsh
# Double-click launcher (Mac): rebuilds the galaxy, starts the server, opens Chrome.
cd "$(dirname "$0")"
python3 build.py
open -a "Google Chrome" "http://localhost:4700"
python3 server.py
