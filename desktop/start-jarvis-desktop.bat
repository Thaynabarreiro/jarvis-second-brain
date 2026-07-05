@echo off
rem Double-click launcher (Windows): starts the system-wide Jarvis with the floating orb.
cd /d "%~dp0"
"%USERPROFILE%\.jarvis\venv\Scripts\python" jarvis.py
pause
