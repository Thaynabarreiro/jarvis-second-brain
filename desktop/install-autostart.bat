@echo off
rem Registers Jarvis and its standby listener as Windows scheduled tasks that
rem run at logon, matching the Mac LaunchAgent setup. The sentinel task
rem repeats every 1 minute indefinitely, so if it exits after handing off to
rem the full app (or if it ever crashes), Task Scheduler brings it back -
rem the same "say Hey Jarvis even after a full quit" behavior as on Mac.
setlocal
set DESKTOP_DIR=%~dp0
set DESKTOP_DIR=%DESKTOP_DIR:~0,-1%
set PYTHON=%USERPROFILE%\.jarvis\venv\Scripts\pythonw.exe

schtasks /create /tn "Jarvis Assistant" /tr "\"%PYTHON%\" \"%DESKTOP_DIR%\jarvis.py\"" /sc onlogon /rl limited /f
schtasks /create /tn "Jarvis Sentinel" /tr "\"%PYTHON%\" \"%DESKTOP_DIR%\wake_sentinel.py\"" /sc onlogon /rl limited /f
schtasks /create /tn "Jarvis Sentinel Watchdog" /tr "schtasks /run /tn \"Jarvis Sentinel\"" /sc minute /mo 1 /f

echo.
echo Done. Jarvis starts at login, and a watchdog task checks every minute
echo that the standby listener is alive (Task Scheduler skips it if it's
echo already running, and restarts it if it isn't) - so "Hey Jarvis" or two
echo claps bring the full app back even after a complete quit.
echo.
echo NOTE: this was written to mirror the Mac version's behavior but could
echo not be tested on a real Windows machine. If "Hey Jarvis" doesn't revive
echo Jarvis after quitting it, open Task Scheduler and check these three
echo tasks ran without errors, or just use start-jarvis-desktop.bat again.
pause
