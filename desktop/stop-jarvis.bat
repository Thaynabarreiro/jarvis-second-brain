@echo off
rem Double-click launcher (Windows): stops the running Jarvis daemon, if any.
set PIDFILE=%USERPROFILE%\.jarvis\jarvis.pid
if exist "%PIDFILE%" (
  set /p PID=<"%PIDFILE%"
  taskkill /PID %PID% /F >nul 2>&1
  del "%PIDFILE%"
  echo Jarvis stopped.
) else (
  echo Jarvis wasn't running.
)
pause
