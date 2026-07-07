@echo off
rem Lightweight standby listener (Windows). Put a shortcut to this file in
rem your Startup folder (Win+R, type shell:startup) alongside the shortcut
rem to start-jarvis-desktop.bat, so both start at login. If you fully close
rem Jarvis, this sentinel (already running since login) will hear "Hey
rem Jarvis" or two claps and relaunch the full app.
cd /d "%~dp0"
"%USERPROFILE%\.jarvis\venv\Scripts\python" wake_sentinel.py
