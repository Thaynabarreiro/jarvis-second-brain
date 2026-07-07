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
  - `run_claude_code` — hands off real coding/writing work to the Claude Code CLI in a specific
    project folder, with a chosen model and effort level (e.g. "open Claude Code in ~/interviews,
    sonnet, low effort, and draft a study plan"). Runs on whatever Claude Code is logged into on
    this Mac (usually your Claude subscription) - a separate cost/quota from the Anthropic API
    key powering Jarvis's own replies. Note: whatever it writes back still gets read out/replied
    to by Jarvis, which does cost a (usually small) amount of API tokens proportional to its length.
  - `screenshot` — native screen capture of whatever is on screen, any app, no sharing dialogs
  - `search_notes` — searches your markdown second brain (Obsidian vault, iCloud Drive, any markdown folder)
  - `remember` — long-term memory file that persists across sessions
  - `read_calendar` — reads today's (or the next N days') events from the Mac Calendar app
  - `read_google_calendar` — same, from Google Calendar, once you link it (see below)
  - `read_outlook_calendar` — same, from Outlook/Microsoft 365 Calendar, once you link it (see below)
- Optional **Slack bridge** — DM or @mention Jarvis on Slack for the same brain, no voice needed

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
  "orb_y": null,
  "slack_bot_token": "",
  "slack_app_token": "",
  "outlook_client_id": "",
  "provider": "anthropic",
  "nvidia_api_key": "",
  "nvidia_model": "openai/gpt-oss-120b"
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
- "Hey Jarvis — what's on my calendar today?"

---

## 🆓 Free brain option: NVIDIA NIM (optional)

Anthropic's API is what powers Jarvis by default (see the API keys section above) - it's cheap
but not free. If you want a **$0 alternative brain**, NVIDIA hosts several open-weight models for
free via an OpenAI-compatible API. After testing several candidates for personality quality,
speed, and - critically - reliable tool use, **`openai/gpt-oss-120b`** came out clearly ahead:
about 1-2 seconds per reply, correct tool calls, and Portuguese quality close to Claude Sonnet.
(Qwen's larger model technically worked too but took 30-45 seconds per turn - unusable for a
live voice assistant. Mistral Large and the older Nemotron models weren't available on the free
tier at all.)

1. Create a free key at <https://build.nvidia.com/settings/api-keys>.
2. Paste it into `config.json`'s `"nvidia_api_key"` field (leave `"provider": "anthropic"` for now).
3. Restart Jarvis once so it picks up the key.
4. **Click the ⚙ gear that appears in the corner of the orb** → pick **"Anthropic"** or
   **"Grátis (NVIDIA)"** any time - it switches instantly, no restart, no editing files.

**About screen vision on the free brain:** `gpt-oss-120b` itself can't see images, but you don't
lose the feature - ask "what's on my screen?" while on the free brain and it automatically
borrows a vision-capable Anthropic call just for that one look, then hands the description back
to the free brain to keep talking. Slightly less private and not literally free for that one
call, but the capability doesn't disappear. Everything else (notes, calendars, run_command,
run_claude_code, memory, Slack) works identically on both brains.

**Image generation:** not wired in yet - NVIDIA's image models live on a different API surface
than the chat models tested here, so this is a genuine follow-up, not something quietly faked.

## 📅 Google Calendar setup (optional)

The Mac Calendar app already works out of the box (native, no setup). To also read a Google
Calendar (e.g. a work calendar not synced to Mac Calendar):

1. Go to <https://console.cloud.google.com>, create a project (or reuse one), then
   **APIs & Services → Enable APIs → search "Google Calendar API" → Enable**.
2. **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
   Application type: **Desktop app**. Download the JSON file it gives you.
3. Save that file as `~/.jarvis/google_credentials.json` (Mac) or
   `%USERPROFILE%\.jarvis\google_credentials.json` (Windows). Rename it exactly to that.
4. Run once from a terminal, inside `desktop/`:
   ```bash
   ~/.jarvis/venv/bin/python google_calendar_setup.py       # Mac
   %USERPROFILE%\.jarvis\venv\Scripts\python google_calendar_setup.py   # Windows
   ```
   Your browser opens, you log in and click Allow. Done — the token is cached and refreshes
   itself; you won't need to repeat this unless you revoke access.

## 📆 Outlook Calendar setup (optional)

To read a Microsoft 365 / Outlook.com calendar:

1. Go to <https://portal.azure.com> → search **"App registrations"** → **New registration**.
   - Name: "Jarvis" (or anything)
   - Supported account types: **"Accounts in any organizational directory and personal Microsoft
     accounts"** (needed for personal outlook.com/hotmail accounts too)
   - Redirect URI: leave blank
   - Click **Register**
2. On the app's overview page, copy the **Application (client) ID**.
3. **Authentication** (left sidebar) → scroll to **Advanced settings** →
   **"Allow public client flows"** → set to **Yes** → **Save**.
4. **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions** →
   search `Calendars.Read` → add it. (No admin approval needed for personal use.)
5. Paste the client ID into `config.json`:
   ```json
   "outlook_client_id": "your-application-client-id"
   ```
6. Run once from a terminal, inside `desktop/`:
   ```bash
   ~/.jarvis/venv/bin/python outlook_calendar_setup.py       # Mac
   %USERPROFILE%\.jarvis\venv\Scripts\python outlook_calendar_setup.py   # Windows
   ```
   It prints a short code and a link to **microsoft.com/devicelogin** — open that link on any
   device, enter the code, sign in with your Microsoft account. Done — the token is cached and
   refreshes itself.

## 💬 Slack setup (optional)

Lets you DM or @mention Jarvis on Slack and get the same brain that answers your voice — a
**separate, dedicated Slack app**, independent from any other bot you already run (e.g. a
Hermes agent for a different project). It won't touch or interfere with that.

1. Go to <https://api.slack.com/apps> → **Create New App → From scratch**. Name it (e.g. "Jarvis"),
   pick your workspace.
2. **Socket Mode** (left sidebar) → toggle it **On** → it'll ask you to generate an
   app-level token: name it anything, scope `connections:write` → copy the token
   (starts with `xapp-`) → this is `slack_app_token`.
3. **OAuth & Permissions** → scroll to **Scopes → Bot Token Scopes** → add:
   `chat:write`, `im:history`, `im:read`, `im:write`, `app_mentions:read`.
4. **Event Subscriptions** → toggle **On** → under **Subscribe to bot events** add:
   `message.im` and `app_mention`.
5. Back in **OAuth & Permissions**, click **Install to Workspace** → copy the
   **Bot User OAuth Token** (starts with `xoxb-`) → this is `slack_bot_token`.
6. Paste both into `config.json`:
   ```json
   "slack_bot_token": "xoxb-…",
   "slack_app_token": "xapp-…"
   ```
7. Restart Jarvis. In Slack, DM the bot directly, or @mention it in any channel it's in.

Slack messages go through the exact same brain as voice — including `run_command`, so you can
ask it to edit, create, or update a note (Obsidian or any file) straight from Slack, e.g.
"add a line to my pricing note about the new plan." It really writes to the file, not just talks
about it.

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
