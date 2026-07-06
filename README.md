# Jarvis — System-Wide AI Butler 🎩

A professional, open-source-stack voice assistant that runs on your machine — not in a browser
tab. Say **"Hey Jarvis"** from any app, and a floating particle orb wakes up, listens, thinks,
and talks back. It knows your notes, sees your screen, runs commands, downloads files, and
remembers what you teach it.

Two versions live in this repo:

| Version | What it is | Needs |
|---|---|---|
| **Desktop (recommended)** — `desktop/` | System-wide daemon: wake word, offline speech-to-text, neural voice, floating always-on-top orb, shell + screen + notes + memory tools | Python 3.10+, an Anthropic API key |
| **Web galaxy** — `viewer/` + `server.py` | 3D knowledge galaxy of your notes in Chrome with voice chat and fly-to-source camera | Python 3, Chrome |

## The stack (all open source except the brain)

- [openWakeWord](https://github.com/dscripka/openWakeWord) — "Hey Jarvis" detection, fully offline
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — speech-to-text, fully offline
- [edge-tts](https://github.com/rany2/edge-tts) — natural neural voices, free
- [pywebview](https://github.com/r0x0r/pywebview) — the floating orb overlay
- **Anthropic API** — the agentic brain, with tools:
  - `run_command` — shell access: download files, open apps, manage files (destructive commands are blocked)
  - `screenshot` — native screen capture of whatever is on screen, any app, no sharing dialogs
  - `search_notes` — searches your markdown second brain (Obsidian vault, iCloud Drive, any markdown folder)
  - `remember` — long-term memory file that persists across sessions
  - `read_calendar` — reads today's (or the next N days') events from the Mac Calendar app

Wake it three ways: say **"Hey Jarvis"**, **clap twice**, or **click the orb**.
Speak over it ("Hey Jarvis…") to interrupt mid-sentence. After he answers, he keeps listening
for **6 seconds** without needing the wake word again, for a natural back-and-forth.

The first time you ask about your calendar, **macOS will show a permission popup** ("Terminal"
or "Python" wants to control Calendar) — click Allow. If you miss it or say no, Jarvis will tell
you exactly where to fix it (System Settings → Privacy & Security → Automation).

---

## 🔑 API keys you need (this is the complete list)

**One key. That's it: an Anthropic API key.**

1. Create it at <https://console.anthropic.com> → API Keys ($5 of credit goes a long way).
2. After running the installer, open `~/.jarvis/config.json` (Mac) or
   `C:\Users\YOU\.jarvis\config.json` (Windows) and paste it into `"api_key"`.
   Type it into the file yourself — never paste API keys into chat windows or websites.

Everything else (wake word, speech-to-text, voice, orb) is free and runs locally.
No OpenAI key, no ElevenLabs, no subscriptions.

---

## 🍎 Mac install

```bash
cd desktop
./install.sh          # one time: creates ~/.jarvis/venv, downloads models
```

Put your API key in `~/.jarvis/config.json`, then double-click **`Jarvis-Desktop.command`**
(first time: right-click → Open). macOS will ask for **Microphone** and **Screen Recording**
permissions — allow both (System Settings → Privacy & Security).

## 🪟 Windows install

1. Install Python 3.10+ from <https://www.python.org/downloads/windows/> —
   check **"Add python.exe to PATH"** in the installer.
2. Download this repo: green **Code → Download ZIP** button, extract to e.g. `C:\jarvis`.
3. Double-click `desktop\install.bat` (one time, downloads ~600 MB of local models).
4. Put your API key in `C:\Users\YOU\.jarvis\config.json`.
5. Double-click `desktop\start-jarvis-desktop.bat`. Allow microphone access if asked.

## Starting and stopping Jarvis

Double-clicking the start file opens a Terminal/Command Prompt window that runs Jarvis in the
background - closing that window does **not** stop it, and double-clicking start again will
refuse to launch a second copy (it detects the one already running instead of duplicating it).

To quit Jarvis, either:
- **Hold the orb down for about a second** - it dims and closes, no window-hunting needed, or
- Double-click **`Stop-Jarvis.command`** (Mac) / **`stop-jarvis.bat`** (Windows) in `desktop/`.

## ⚙️ config.json reference

```json
{
  "api_key": "sk-ant-…",
  "model": "claude-sonnet-5",
  "voice": "pt-BR-AntonioNeural",
  "language": "pt",
  "notes_dir": "/path/to/your/obsidian/vault",
  "user_title": "senhora",
  "orb_x": null,
  "orb_y": null
}
```

- `model`: `claude-sonnet-5` is the default for a snappy voice assistant. Switch to `claude-opus-4-8` for a smarter but slower brain.
- `voice`: any edge-tts voice (`edge-tts --list-voices`), e.g. `en-GB-RyanNeural` for English
- `language`: speech-recognition language (`pt`, `en`, …)
- `notes_dir`: your markdown notes folder; leave `""` to disable notes search
- `user_title`: how the butler addresses you (`sir`, `senhora`, …)
- `orb_x` / `orb_y`: remembers where you last dragged the orb to rest; leave `null` for bottom-right

### The orb's behavior

It rests in the bottom-right corner (or wherever you last dragged it) when idle, and glides to the
center of the screen while listening, thinking, or speaking. **Drag it anywhere** with the mouse —
its new resting spot is remembered automatically, even after restarting Jarvis.

## Try saying

- "Hey Jarvis — what's on my screen right now?"
- "Hey Jarvis — search my notes for the pricing strategy."
- "Hey Jarvis — download the latest n8n release to my Downloads folder."
- "Hey Jarvis — remember that my husband's laptop uses the English voice."

---

## Web galaxy version (bonus)

The original 3D knowledge galaxy still works: `python3 build.py && python3 server.py`,
then open <http://localhost:4700> in Chrome. Same `config.example.json` → `config.json` setup
in the repo root. See commit history for its full feature set (wake word in browser,
clap detection, screen sharing, remember-that notes).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Orb doesn't hear you | Check OS microphone permission for the terminal/Python |
| "Screen recording" black images (Mac) | System Settings → Privacy → Screen Recording → allow Python |
| Voice sounds wrong language | Set `voice` and `language` in config.json |
| First answer is slow | Models warm up on first run; it gets faster |
| `python` not recognized (Win) | Reinstall Python with "Add to PATH" checked |

Built with Claude Code. Wake-word, STT, TTS and overlay are fully open source.
