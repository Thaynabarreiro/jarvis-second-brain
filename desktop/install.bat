@echo off
rem One-time installer (Windows): creates the venv at %USERPROFILE%\.jarvis\venv and installs everything.
cd /d "%~dp0"
python -m venv "%USERPROFILE%\.jarvis\venv"
"%USERPROFILE%\.jarvis\venv\Scripts\pip" install --upgrade pip
"%USERPROFILE%\.jarvis\venv\Scripts\pip" install -r requirements.txt
"%USERPROFILE%\.jarvis\venv\Scripts\python" -c "import openwakeword.utils as u; u.download_models(['hey_jarvis'])"
"%USERPROFILE%\.jarvis\venv\Scripts\python" -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
echo.
echo Installed. Now put your Anthropic API key in %USERPROFILE%\.jarvis\config.json, then double-click start-jarvis-desktop.bat
pause
