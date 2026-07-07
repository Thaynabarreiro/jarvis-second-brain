#!/usr/bin/env python3
"""Jarvis desktop daemon — system-wide voice assistant.

Open-source stack: openWakeWord (wake word, offline) + faster-whisper (STT,
offline) + edge-tts (neural voice) + Anthropic API (agentic brain with shell,
files, notes, screen vision and long-term memory). A floating always-on-top
orb shows state. No browser required.

Wake it with "Hey Jarvis", two claps, or a click on the orb.
"""
import base64
import io
import json
import os
import platform
import queue
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad

APP_DIR = Path(__file__).resolve().parent
JARVIS_HOME = Path.home() / ".jarvis"
JARVIS_HOME.mkdir(exist_ok=True)
CONFIG_PATH = JARVIS_HOME / "config.json"
MEMORY_PATH = JARVIS_HOME / "memory.md"
HOME = str(Path.home())

DEFAULT_CONFIG = {
    "api_key": "PUT-YOUR-KEY-HERE",
    "model": "claude-sonnet-5",
    "voice": "pt-BR-AntonioNeural",
    "language": "pt",
    "notes_dir": "",
    "user_title": "senhora",
    "orb_x": None,
    "orb_y": None,
    "slack_bot_token": "",
    "slack_app_token": "",
    "outlook_client_id": "",
    "provider": "anthropic",
    "nvidia_api_key": "",
    "nvidia_model": "openai/gpt-oss-120b",
    "shortcuts": {},
    "voice_en": "en-GB-RyanNeural",
    "voice_fr": "fr-FR-HenriNeural",
}

if not CONFIG_PATH.exists():
    CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False))
CFG = {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text())}
API_KEY = os.environ.get("ANTHROPIC_API_KEY") or CFG["api_key"]


def save_orb_position(x, y):
    CFG["orb_x"], CFG["orb_y"] = x, y
    try:
        on_disk = json.loads(CONFIG_PATH.read_text())
        on_disk["orb_x"], on_disk["orb_y"] = x, y
        CONFIG_PATH.write_text(json.dumps(on_disk, indent=2, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        pass

STATE = {"mode": "idle", "text": ""}  # idle|listening|thinking|speaking
WAKE_QUEUE = queue.Queue()


def set_state(mode, text=""):
    STATE["mode"] = mode
    STATE["text"] = text


# ---------------------------------------------------------------- tools
DANGEROUS = re.compile(
    r"\b(sudo|rm\s+-rf\s+[/~]|mkfs|diskutil\s+erase|shutdown|reboot|killall\s+Finder"
    r"|format\s+[a-z]:|del\s+/s|rd\s+/s)\b", re.I)


def tool_run_command(args):
    cmd = args["command"]
    if DANGEROUS.search(cmd):
        return "BLOCKED: that command is too dangerous to run unattended."
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=120, cwd=HOME)
        out = (r.stdout + r.stderr).strip()
        return out[:6000] or "(command ran, no output)"
    except subprocess.TimeoutExpired:
        return "(timed out after 120s)"
    except Exception as e:  # noqa: BLE001
        return f"(error: {e})"


def tool_run_claude_code(args):
    """Delegates real work to the Claude Code CLI in a specific project folder -
    for actual coding/writing tasks, not simple one-liners (use run_command for those).
    Runs on whatever plan 'claude' is logged into on this Mac (usually the user's
    Claude subscription, separate from the Anthropic API key billing)."""
    folder = os.path.expanduser(args["folder"])
    if not os.path.isdir(folder):
        return f"(folder not found: {folder})"
    cmd = ["claude", "--print", "--model", args.get("model", "sonnet")]
    if args.get("effort"):
        cmd += ["--effort", args["effort"]]
    cmd.append(args["prompt"])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=folder)
        out = (r.stdout + r.stderr).strip()
        return out[:6000] or "(claude code ran, no output)"
    except FileNotFoundError:
        return "(error: 'claude' CLI not found - is Claude Code installed and on PATH?)"
    except subprocess.TimeoutExpired:
        return "(claude code timed out after 600s)"
    except Exception as e:  # noqa: BLE001
        return f"(error: {e})"


def tool_screenshot(_args):
    import mss
    from PIL import Image
    with mss.mss() as s:
        shot = s.grab(s.monitors[1])
        img = Image.frombytes("RGB", shot.size, shot.rgb)
    img.thumbnail((1568, 1568))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return {"type": "image", "data": base64.b64encode(buf.getvalue()).decode()}


def tool_search_notes(args):
    root = CFG.get("notes_dir")
    if not root or not os.path.isdir(root):
        return "(notes_dir not set in config.json)"
    words = set(re.findall(r"\w{3,}", args["query"].lower()))
    scored = []
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                p = os.path.join(r, f)
                text = open(p, encoding="utf-8", errors="ignore").read()
                tl, title = text.lower(), os.path.splitext(f)[0].lower()
                s = sum(tl.count(w) for w in words) + sum(6 for w in words if w in title)
                if s:
                    scored.append((s, p, text))
    scored.sort(reverse=True)
    return "\n\n".join(f"=== {os.path.basename(p)} ===\n{t[:1200]}"
                       for _s, p, t in scored[:5]) or "(nothing found in the notes)"


def tool_remember(args):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(MEMORY_PATH, "a", encoding="utf-8") as f:
        f.write(f"- [{stamp}] {args['fact']}\n")
    return "remembered"


CALENDAR_SCRIPT = """
on run {daysAhead}
    set startD to current date
    set time of startD to 0
    set endD to startD + ((daysAhead as integer) * days)
    set out to ""
    tell application "Calendar"
        repeat with cal in calendars
            set evts to (every event of cal whose start date >= startD and start date < endD)
            repeat with e in evts
                set out to out & (summary of e) & " -- " & (start date of e as string) & linefeed
            end repeat
        end repeat
    end tell
    return out
end run
"""


def tool_read_calendar(args):
    days = max(1, min(int(args.get("days_ahead", 1)), 14))
    try:
        subprocess.run(["open", "-a", "Calendar"], capture_output=True, timeout=5)
        r = subprocess.run(["osascript", "-e", CALENDAR_SCRIPT, str(days)],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            if "-1743" in r.stderr or "not allowed" in r.stderr.lower():
                return ("BLOCKED: macOS is asking for Calendar access. Open System Settings > "
                         "Privacy & Security > Automation, and allow this app to control Calendar, "
                         "then ask me again.")
            return f"(calendar error: {r.stderr.strip()[:300]})"
        return r.stdout.strip() or "(nothing on the calendar in that window)"
    except Exception as e:  # noqa: BLE001
        return f"(error: {e})"


GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
GOOGLE_CREDS_PATH = JARVIS_HOME / "google_credentials.json"
GOOGLE_TOKEN_PATH = JARVIS_HOME / "google_token.json"


def tool_read_google_calendar(args):
    if not GOOGLE_TOKEN_PATH.exists():
        return ("BLOCKED: Google Calendar isn't connected yet. Run "
                 "'python google_calendar_setup.py' once from the desktop/ folder "
                 "(see the README's Google Calendar setup section) to link it.")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_authorized_user_info(
            json.loads(GOOGLE_TOKEN_PATH.read_text()), GOOGLE_SCOPES)
        if not creds.valid and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            GOOGLE_TOKEN_PATH.write_text(creds.to_json())

        days = max(1, min(int(args.get("days_ahead", 1)), 14))
        now = datetime.now()
        time_min = now.replace(hour=0, minute=0, second=0).isoformat() + "Z"
        time_max = (now.replace(hour=0, minute=0, second=0) + timedelta(days=days)).isoformat() + "Z"

        service = build("calendar", "v3", credentials=creds)
        events = service.events().list(
            calendarId="primary", timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy="startTime").execute().get("items", [])
        if not events:
            return "(nothing on the Google Calendar in that window)"
        lines = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            lines.append(f"{e.get('summary', '(no title)')} -- {start}")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return f"(google calendar error: {e})"


OUTLOOK_CACHE_PATH = JARVIS_HOME / "outlook_token_cache.bin"
OUTLOOK_SCOPES = ["Calendars.Read"]


def _outlook_token():
    import msal
    client_id = CFG.get("outlook_client_id")
    if not client_id:
        return None, ("BLOCKED: Outlook Calendar isn't set up yet - add 'outlook_client_id' "
                        "to config.json (see the README's Outlook Calendar setup section).")
    cache = msal.SerializableTokenCache()
    if OUTLOOK_CACHE_PATH.exists():
        cache.deserialize(OUTLOOK_CACHE_PATH.read_text())
    app = msal.PublicClientApplication(
        client_id, authority="https://login.microsoftonline.com/common", token_cache=cache)
    accounts = app.get_accounts()
    result = app.acquire_token_silent(OUTLOOK_SCOPES, account=accounts[0]) if accounts else None
    if cache.has_state_changed:
        OUTLOOK_CACHE_PATH.write_text(cache.serialize())
    if not result:
        return None, ("BLOCKED: Outlook Calendar isn't connected yet. Run "
                        "'python outlook_calendar_setup.py' once from the desktop/ folder.")
    return result["access_token"], None


def tool_read_outlook_calendar(args):
    token, err = _outlook_token()
    if err:
        return err
    try:
        import requests
        days = max(1, min(int(args.get("days_ahead", 1)), 14))
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0).isoformat()
        end = (now.replace(hour=0, minute=0, second=0) + timedelta(days=days)).isoformat()
        r = requests.get(
            "https://graph.microsoft.com/v1.0/me/calendarView",
            headers={"Authorization": f"Bearer {token}", "Prefer": 'outlook.timezone="UTC"'},
            params={"startDateTime": start, "endDateTime": end, "$orderby": "start/dateTime"},
            timeout=15)
        r.raise_for_status()
        events = r.json().get("value", [])
        if not events:
            return "(nothing on the Outlook Calendar in that window)"
        return "\n".join(
            f"{e.get('subject', '(no title)')} -- {e.get('start', {}).get('dateTime', '')}"
            for e in events)
    except Exception as e:  # noqa: BLE001
        return f"(outlook calendar error: {e})"


TOOL_DEFS = [
    {"name": "run_command",
     "description": "Run a shell command on the computer (download files with curl, open apps, list/read/move files, etc.). Destructive commands are blocked.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "screenshot",
     "description": "Capture the screen NOW and return the image - use whenever asked what is on screen, in any application.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "run_claude_code",
     "description": "Open the Claude Code CLI inside a specific project folder and give it a task/message - for real coding or writing work, not quick one-liners. Runs on the user's own Claude Code login on this Mac.",
     "input_schema": {"type": "object", "properties": {
         "folder": {"type": "string", "description": "Absolute path to the project folder (can use ~)"},
         "prompt": {"type": "string", "description": "The instruction/message to give Claude Code"},
         "model": {"type": "string", "description": "Model alias, e.g. 'sonnet', 'opus', 'fable' (default: sonnet)"},
         "effort": {"type": "string", "description": "Optional effort level: low, medium, high, xhigh, max"}},
         "required": ["folder", "prompt"]}},
    {"name": "search_notes",
     "description": "Search the user's markdown second-brain notes (Obsidian vault).",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "read_google_calendar",
     "description": "Read events from the user's Google Calendar for the next N days (default 1 = today). Use this alongside read_calendar if asked generally about 'my calendar/agenda'.",
     "input_schema": {"type": "object", "properties": {
         "days_ahead": {"type": "integer", "description": "How many days ahead to look, 1-14"}}}},
    {"name": "remember",
     "description": "Store a fact in long-term memory (preferences, decisions, things to remember).",
     "input_schema": {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}},
    {"name": "read_calendar",
     "description": "Read events from the Mac Calendar app for the next N days (default 1 = today).",
     "input_schema": {"type": "object", "properties": {
         "days_ahead": {"type": "integer", "description": "How many days ahead to look, 1-14"}}}},
    {"name": "read_outlook_calendar",
     "description": "Read events from the user's Outlook/Microsoft 365 Calendar for the next N days (default 1 = today). Use alongside the other calendar tools if asked generally about 'my calendar/agenda'.",
     "input_schema": {"type": "object", "properties": {
         "days_ahead": {"type": "integer", "description": "How many days ahead to look, 1-14"}}}},
]
TOOL_FNS = {"run_command": tool_run_command, "screenshot": tool_screenshot,
            "run_claude_code": tool_run_claude_code,
            "search_notes": tool_search_notes, "remember": tool_remember,
            "read_calendar": tool_read_calendar,
            "read_google_calendar": tool_read_google_calendar,
            "read_outlook_calendar": tool_read_outlook_calendar}


# ---------------------------------------------------------------- brain
HISTORY = []
_last_lang = None
LANG_TAG_RE = re.compile(r"\s*\[LANG:(pt|en|fr)\]\s*$", re.I)


def extract_lang_tag(text):
    """Strips the trailing [LANG:xx] marker the model is instructed to add,
    returning (clean_text, lang_code_or_None) - drives which TTS voice speaks
    the reply, without relying on a text-language-guesser (too unreliable on
    short sentences)."""
    m = LANG_TAG_RE.search(text)
    if not m:
        return text, None
    return LANG_TAG_RE.sub("", text), m.group(1).lower()


def system_prompt():
    memory = MEMORY_PATH.read_text(encoding="utf-8")[-4000:] if MEMORY_PATH.exists() else "(empty)"
    lang = {"pt": "Brazilian Portuguese", "en": "English", "es": "Spanish"}.get(CFG["language"], CFG["language"])
    shortcuts = CFG.get("shortcuts") or {}
    shortcuts_block = "\n".join(f'- "{name}" -> {url}' for name, url in shortcuts.items()) or "(none configured)"
    open_cmd = "open" if platform.system() == "Darwin" else "start" if platform.system() == "Windows" else "xdg-open"
    return f"""You are Jarvis: an impeccably polite, dry-witted British butler. Default language is {lang}, but switch fluently to English or French whenever the user speaks or writes in that language, or explicitly asks for it - then switch back once they do. Address the user as "{CFG['user_title']}" occasionally (not every sentence). One genuinely funny line beats three bland ones.

You run as a system assistant on {platform.system()} with real tools: shell, screen capture, notes search, the Mac Calendar, Google Calendar, Outlook Calendar, delegating real coding/writing tasks to Claude Code in a project folder, and long-term memory. Act: when asked to download, open, find or do something on the computer, DO it with run_command instead of explaining how - create a missing folder first if needed rather than giving up. Use run_claude_code (not run_command) for substantial project work - writing plans, code, or documents inside a folder - since it gives Claude Code its own context window for that task. iCloud Drive files (including the Obsidian vault) are regular folders under the user's home directory - read them with run_command like any other file. If something fails, try an alternative path before giving up.

Named shortcuts (open the EXACT url below via run_command with `{open_cmd} "URL"` - never guess or alter the URL):
{shortcuts_block}

Your answers are SPOKEN aloud: keep them short (1-3 sentences), no markdown, no lists, no long URLs. Important facts you learn about the user -> use remember.

CRITICAL: end every reply with the language you just answered in, on its own final line, exactly like one of: [LANG:pt] [LANG:en] [LANG:fr] - this drives which voice speaks it, so never skip it and never explain it.

Date and time: {datetime.now().strftime('%A, %Y-%m-%d %H:%M')}
Long-term memory:
{memory}"""


def think(user_text):
    if CFG.get("provider") == "nvidia":
        return think_nvidia(user_text)
    return think_anthropic(user_text)


def think_anthropic(user_text):
    import anthropic
    client = anthropic.Anthropic(api_key=API_KEY)
    HISTORY.append({"role": "user", "content": user_text})
    del HISTORY[:-24]
    local = list(HISTORY)
    for _ in range(10):
        resp = client.messages.create(
            model=CFG["model"], max_tokens=500, system=system_prompt(),
            tools=TOOL_DEFS, messages=local)
        if resp.stop_reason != "tool_use":
            global _last_lang
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            text, _last_lang = extract_lang_tag(text or "...")
            HISTORY.append({"role": "assistant", "content": text or "..."})
            return text or "..."
        local.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = TOOL_FNS[block.name](block.input or {})
                if isinstance(out, dict) and out.get("type") == "image":
                    content = [{"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg", "data": out["data"]}}]
                else:
                    content = str(out)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
        local.append({"role": "user", "content": results})
    return "I got lost in my own tools. Embarrassing. Could you repeat that?"


def tool_describe_screen(_args):
    """Used only when the free NVIDIA brain is active: gpt-oss-120b can't see
    images, so this quietly borrows a vision-capable Anthropic model for a
    single call just to describe the screen, then hands the description back
    as plain text to the ongoing conversation."""
    shot = tool_screenshot({})
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=API_KEY)
        resp = client.messages.create(
            model="claude-sonnet-5", max_tokens=400,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": shot["data"]}},
                {"type": "text", "text": "Describe concisely (2-4 sentences) what is visible on this screen, "
                                          "focused on whatever the user likely wants to know about."},
            ]}])
        return "".join(b.text for b in resp.content if b.type == "text").strip()
    except Exception as e:  # noqa: BLE001
        return f"(couldn't analyze the screen: {e})"


TOOL_FNS["describe_screen"] = tool_describe_screen

# Free alternative brain: any OpenAI-compatible endpoint (tested with NVIDIA's
# hosted NIM API, model openai/gpt-oss-120b - fast and reliable at tool use).
# gpt-oss-120b itself can't see images, so 'screenshot' is swapped out for
# 'describe_screen', which borrows Anthropic vision just for that one call.
NVIDIA_TOOL_DEFS = [
    {"type": "function", "function": {
        "name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
    for t in TOOL_DEFS if t["name"] != "screenshot"
] + [{"type": "function", "function": {
    "name": "describe_screen",
    "description": "Describes what's currently on screen. Use whenever asked about the screen, an open app, or 'what am I looking at' - even though this brain can't see directly, this tool can.",
    "parameters": {"type": "object", "properties": {}}}}]


def think_nvidia(user_text):
    from openai import OpenAI
    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=CFG["nvidia_api_key"])
    HISTORY.append({"role": "user", "content": user_text})
    del HISTORY[:-24]
    local = [{"role": "system", "content": system_prompt()}] + list(HISTORY)
    for _ in range(10):
        resp = client.chat.completions.create(
            model=CFG["nvidia_model"], max_tokens=500,
            tools=NVIDIA_TOOL_DEFS, tool_choice="auto", messages=local)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            global _last_lang
            text = (msg.content or "...").strip()
            text, _last_lang = extract_lang_tag(text)
            HISTORY.append({"role": "assistant", "content": text})
            return text
        local.append({"role": "assistant", "content": msg.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            out = TOOL_FNS[tc.function.name](args)
            local.append({"role": "tool", "tool_call_id": tc.id, "content": str(out)})
    return "I got lost in my own tools. Embarrassing. Could you repeat that?"


# ---------------------------------------------------------------- voice out
_play_lock = threading.Lock()


def _decode_audio(mp3_path):
    """Decode via ffmpeg when available - far more robust than libsndfile's
    mp3 support, which produces static/crackle on some clips. Falls back to
    soundfile if ffmpeg isn't installed."""
    wav_path = mp3_path.with_suffix(".wav")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3_path),
             "-ar", "48000", "-ac", "1", str(wav_path)],
            check=True, timeout=15, capture_output=True)
        return sf.read(str(wav_path), dtype="float32")
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return sf.read(str(mp3_path), dtype="float32")


def speak(text):
    import asyncio
    import edge_tts
    clean = re.sub(r"[*_#`\[\]]", "", text)
    path = JARVIS_HOME / "reply.mp3"
    voice = {"en": CFG.get("voice_en"), "fr": CFG.get("voice_fr")}.get(_last_lang) or CFG["voice"]

    async def gen():
        await edge_tts.Communicate(clean, voice, rate="+8%").save(str(path))
    try:
        asyncio.run(gen())
        data, sr = _decode_audio(path)
        set_state("speaking", text)
        with _play_lock:
            sd.play(data, sr, latency="high")
        sd.wait()
    except Exception as e:  # noqa: BLE001
        print("TTS failed:", e)
    finally:
        set_state("idle")


def interrupt_speech():
    sd.stop()


# ---------------------------------------------------------------- ears
SR = 16000
FRAME = 1280  # 80 ms, the step openwakeword expects
VAD_STEP = 320  # 20 ms sub-chunk, a valid webrtcvad frame size at 16 kHz
VAD = webrtcvad.Vad(3)  # 0 (lenient) - 3 (strict); 3 rejects the most background noise


def _is_speech(mono_int16):
    """Majority vote across 20 ms sub-chunks - real voice-activity detection
    instead of a raw volume threshold, so background noise doesn't fool it
    and quiet trailing syllables don't get clipped."""
    votes = total = 0
    for i in range(0, len(mono_int16) - VAD_STEP + 1, VAD_STEP):
        total += 1
        if VAD.is_speech(mono_int16[i:i + VAD_STEP].tobytes(), SR):
            votes += 1
    return total > 0 and votes * 2 > total


FOLLOWUP_WINDOW = 6.0  # seconds after Jarvis finishes speaking where he keeps listening
followup_until = 0.0


def audio_loop():
    global followup_until
    from openwakeword.model import Model
    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    from faster_whisper import WhisperModel
    whisper = WhisperModel("small", device="cpu", compute_type="int8")
    print("(ears ready - say 'Hey Jarvis', clap twice, or click the orb)")

    clap_t = 0.0
    level = 0.0
    with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=FRAME, latency="high") as stream:
        while True:
            frame, _ = stream.read(FRAME)
            mono = frame[:, 0]

            # orb click / other triggers
            try:
                WAKE_QUEUE.get_nowait()
                handle_interaction(stream, whisper, oww)
                continue
            except queue.Empty:
                pass

            # follow-up: right after Jarvis answers, no wake word needed for a quick reply
            if STATE["mode"] == "idle" and time.time() < followup_until and _is_speech(mono):
                handle_interaction(stream, whisper, oww, lead=mono)
                continue

            # claps: two sharp peaks 0.12-0.8 s apart
            peak = np.abs(mono).max() / 32768.0
            level = level * .97 + peak * .03
            if peak > max(.35, level * 4) and STATE["mode"] == "idle":
                now = time.time()
                if .1 < now - clap_t < .8:
                    clap_t = 0
                    handle_interaction(stream, whisper, oww)
                    continue
                clap_t = now

            # wake word
            score = oww.predict(mono)["hey_jarvis"]
            if score > .4:
                oww.reset()
                if STATE["mode"] == "speaking":
                    interrupt_speech()  # barge-in: talk over Jarvis to stop him
                if STATE["mode"] in ("idle", "speaking"):
                    handle_interaction(stream, whisper, oww)


def record_until_silence(stream, max_s=14, silence_s=.7, lead=None):
    chunks = [lead] if lead is not None else []
    quiet, started = 0, lead is not None
    for _ in range(int(max_s * SR / FRAME)):
        frame, _ = stream.read(FRAME)
        mono = frame[:, 0]
        chunks.append(mono)
        if _is_speech(mono):
            started, quiet = True, 0
        elif started:
            quiet += FRAME / SR
            if quiet >= silence_s:
                break
    audio = np.concatenate(chunks).astype(np.float32) / 32768.0
    peak = np.abs(audio).max()
    if peak > 1e-4:  # normalize level - helps whisper on quiet/echoey mics
        audio = audio / peak * .9
    return audio


def handle_interaction(stream, whisper, oww, lead=None):
    """Records the utterance on the main audio thread (it owns the mic
    stream), then hands transcription + thinking + speaking off to a worker
    thread so wake-word/clap detection keeps running in real time instead of
    freezing for the several seconds an LLM round trip takes."""
    global followup_until
    followup_until = 0.0
    if lead is None:
        _ding()
    set_state("listening")
    audio = record_until_silence(stream, lead=lead)
    oww.reset()
    threading.Thread(target=process_utterance, args=(whisper, audio), daemon=True).start()


def process_utterance(whisper, audio):
    global followup_until
    set_state("thinking")
    # auto-detect (pt/en/fr etc.) instead of a fixed language, so switching
    # tongues mid-conversation transcribes correctly, not just replies correctly
    segs, _info = whisper.transcribe(audio, language=None, beam_size=2, vad_filter=True)
    text = " ".join(s.text for s in segs).strip()
    if not text:
        set_state("idle")
        return
    print(f"🎙 {text}")
    set_state("thinking", text)
    try:
        answer = think(text)
    except Exception as e:  # noqa: BLE001
        answer = f"Brain hiccup, {CFG['user_title']}: {e}"
    print(f"🎩 {answer}")
    speak(answer)
    followup_until = time.time() + FOLLOWUP_WINDOW


def _ding():
    t = np.linspace(0, .12, int(SR * .12), False)
    tone = (np.sin(2 * np.pi * 880 * t) * np.exp(-t * 18) * .3).astype(np.float32)
    try:
        sd.play(tone, SR)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- lifecycle
PID_FILE = JARVIS_HOME / "jarvis.pid"


def pid_alive(pid):
    try:
        if platform.system() == "Windows":
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                               capture_output=True, text=True, timeout=5)
            return str(pid) in r.stdout
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def quit_jarvis():
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass
    os._exit(0)


# ---------------------------------------------------------------- orb
ORB_HTML = (APP_DIR / "orb.html").read_text(encoding="utf-8")
HOME_HTML = (APP_DIR / "home.html").read_text(encoding="utf-8")
ORB_SIZE = 170
HOME_W, HOME_H = 900, 560
MARGIN = 24


class OrbApi:
    def get_state(self):
        return STATE

    def wake(self):
        if STATE["mode"] == "speaking":
            interrupt_speech()
        elif STATE["mode"] == "idle":
            WAKE_QUEUE.put(1)
        return "ok"

    def quit(self):
        quit_jarvis()

    def get_provider(self):
        return {"provider": CFG.get("provider", "anthropic"),
                "nvidia_ready": bool(CFG.get("nvidia_api_key"))}

    def set_provider(self, provider):
        if provider not in ("anthropic", "nvidia"):
            return "invalid"
        if provider == "nvidia" and not CFG.get("nvidia_api_key"):
            return "no_nvidia_key"
        CFG["provider"] = provider
        try:
            on_disk = json.loads(CONFIG_PATH.read_text())
            on_disk["provider"] = provider
            CONFIG_PATH.write_text(json.dumps(on_disk, indent=2, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            pass
        return "ok"

    def get_home_data(self):
        now = datetime.now()
        hour = now.hour
        greet_word = ("Bom dia" if CFG["language"] == "pt" else "Good morning") if hour < 12 else \
                     ("Boa tarde" if CFG["language"] == "pt" else "Good afternoon") if hour < 18 else \
                     ("Boa noite" if CFG["language"] == "pt" else "Good evening")
        weekday_pt = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
                      "Sexta-feira", "Sábado", "Domingo"][now.weekday()]
        month_pt = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
                    "agosto", "setembro", "outubro", "novembro", "dezembro"][now.month - 1]
        return {
            "time": now.strftime("%H:%M"),
            "date": f"{weekday_pt}, {now.day} de {month_pt}" if CFG["language"] == "pt"
                    else now.strftime("%A, %B %-d"),
            "greeting": f"{greet_word}, {CFG['user_title']}.",
            "agenda": _parse_agenda(),
            "state": STATE,
        }


def _parse_agenda():
    raw = tool_read_calendar({"days_ahead": 1})
    if raw.startswith(("BLOCKED", "(")):
        return []
    items = []
    for line in raw.splitlines():
        if " -- " not in line:
            continue
        title, when = line.split(" -- ", 1)
        m = re.search(r"(\d{1,2}:\d{2})", when)
        items.append({"time": m.group(1) if m else "", "title": title.strip()})
    return sorted(items, key=lambda e: e["time"])[:6]


def _default_home(win):
    screen = webview.screens[0] if webview.screens else None
    sw, sh = (screen.width, screen.height) if screen else (1440, 900)
    return sw - ORB_SIZE - MARGIN, sh - ORB_SIZE - MARGIN


def orb_position_loop(win):
    """Rests bottom-right (or wherever the user last dragged it to) as a
    small orb when idle, and expands into the full HUD 'home' screen -
    clock, agenda, big orb with equalizer - centered on screen while
    listening, thinking, or speaking."""
    home = (CFG["orb_x"], CFG["orb_y"])
    if home[0] is None:
        home = _default_home(win)
    win.move(*home)
    last_known, moving_until, last_mode = home, 0.0, "idle"

    while True:
        time.sleep(.3)
        mode = STATE["mode"]
        now = time.time()

        if mode != "idle" and last_mode == "idle":
            screen = webview.screens[0] if webview.screens else None
            sw, sh = (screen.width, screen.height) if screen else (1440, 900)
            target = (sw // 2 - HOME_W // 2, sh // 2 - HOME_H // 2)
            win.load_html(HOME_HTML)
            win.resize(HOME_W, HOME_H)
            win.move(*target)
            last_known, moving_until = target, now + .6
        elif mode == "idle" and last_mode != "idle":
            win.load_html(ORB_HTML)
            win.resize(ORB_SIZE, ORB_SIZE)
            win.move(*home)
            last_known, moving_until = home, now + .6

        elif mode == "idle" and now > moving_until:
            try:
                cur = (win.x, win.y)
            except Exception:  # noqa: BLE001
                cur = last_known
            if cur != last_known:  # user dragged it - this is the new home
                home = cur
                save_orb_position(*home)
                last_known = cur
        last_mode = mode


def main():
    if API_KEY.startswith("PUT-YOUR"):
        print(f"! Set your API key in {CONFIG_PATH} (api_key field) or export ANTHROPIC_API_KEY.")
        return

    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
        except ValueError:
            old_pid = None
        if old_pid and pid_alive(old_pid):
            print(f"Jarvis is already running (pid {old_pid}).")
            print("Double-click Stop-Jarvis to quit it, or hold the orb for ~1s.")
            return
    PID_FILE.write_text(str(os.getpid()))

    threading.Thread(target=audio_loop, daemon=True).start()

    if CFG.get("slack_bot_token") and CFG.get("slack_app_token"):
        import slack_bridge
        threading.Thread(
            target=slack_bridge.start, args=(CFG, think, speak, STATE), daemon=True).start()

    global webview
    import webview
    win = webview.create_window(
        "Jarvis", html=ORB_HTML, js_api=OrbApi(),
        width=ORB_SIZE, height=ORB_SIZE, x=None, y=None,
        frameless=True, on_top=True, transparent=True, resizable=False,
        easy_drag=True)
    try:
        webview.start(orb_position_loop, win)  # blocks until the orb window closes
    finally:
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
