#!/bin/zsh
# One-time installer (Mac): creates the venv at ~/.jarvis/venv and installs everything.
set -e
cd "$(dirname "$0")"
python3 -m venv "$HOME/.jarvis/venv"
"$HOME/.jarvis/venv/bin/pip" install --upgrade pip
"$HOME/.jarvis/venv/bin/pip" install -r requirements.txt
"$HOME/.jarvis/venv/bin/python" -c "import openwakeword.utils as u; u.download_models(['hey_jarvis'])"
"$HOME/.jarvis/venv/bin/python" -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
echo ""
echo "✔ Installed. Now put your Anthropic API key in ~/.jarvis/config.json, then double-click Jarvis-Desktop.command"
