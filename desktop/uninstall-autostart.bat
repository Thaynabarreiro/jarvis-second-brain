@echo off
rem Undoes install-autostart.bat.
schtasks /delete /tn "Jarvis Assistant" /f
schtasks /delete /tn "Jarvis Sentinel" /f
schtasks /delete /tn "Jarvis Sentinel Watchdog" /f
echo Autostart and standby listener tasks removed.
pause
