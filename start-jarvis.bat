@echo off
rem Double-click launcher (Windows): rebuilds the galaxy, starts the server, opens Chrome.
cd /d "%~dp0"
python build.py
start chrome "http://localhost:4700"
python server.py
