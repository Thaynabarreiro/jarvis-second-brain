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
from datetime import datetime
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


TOOL_DEFS = [
    {"name": "run_command",
     "description": "Run a shell command on the computer (download files with curl, open apps, list/read/move files, etc.). Destructive commands are blocked.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "screenshot",
     "description": "Capture the screen NOW and return the image - use whenever asked what is on screen, in any application.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "search_notes",
     "description": "Search the user's markdown second-brain notes (Obsidian vault).",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "remember",
     "description": "Store a fact in long-term memory (preferences, decisions, things to remember).",
     "input_schema": {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}},
]
TOOL_FNS = {"run_command": tool_run_command, "screenshot": tool_screenshot,
            "search_notes": tool_search_notes, "remember": tool_remember}


# ---------------------------------------------------------------- brain
HISTORY = []


def system_prompt():
    memory = MEMORY_PATH.read_text(encoding="utf-8")[-4000:] if MEMORY_PATH.exists() else "(empty)"
    lang = {"pt": "Brazilian Portuguese", "en": "English", "es": "Spanish"}.get(CFG["language"], CFG["language"])
    return f"""You are Jarvis: an impeccably polite, dry-witted British butler. Speak {lang}. Address the user as "{CFG['user_title']}" occasionally (not every sentence). One genuinely funny line beats three bland ones.

You run as a system assistant on {platform.system()} with real tools: shell, screen capture, notes search and long-term memory. Act: when asked to download, open, find or do something on the computer, DO it with run_command instead of explaining how. If something fails, try an alternative path before giving up.

Your answers are SPOKEN aloud: keep them short (1-3 sentences), no markdown, no lists, no long URLs. Important facts you learn about the user -> use remember.

Date and time: {datetime.now().strftime('%A, %Y-%m-%d %H:%M')}
Long-term memory:
{memory}"""


def think(user_text):
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
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
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

    async def gen():
        await edge_tts.Communicate(clean, CFG["voice"], rate="+8%").save(str(path))
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


def audio_loop():
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

            # claps: two sharp peaks 0.12-0.7 s apart
            peak = np.abs(mono).max() / 32768.0
            level = level * .97 + peak * .03
            if peak > max(.5, level * 4) and STATE["mode"] == "idle":
                now = time.time()
                if .12 < now - clap_t < .7:
                    clap_t = 0
                    handle_interaction(stream, whisper, oww)
                    continue
                clap_t = now

            # wake word
            score = oww.predict(mono)["hey_jarvis"]
            if score > .55:
                oww.reset()
                if STATE["mode"] == "speaking":
                    interrupt_speech()  # barge-in: talk over Jarvis to stop him
                if STATE["mode"] in ("idle", "speaking"):
                    handle_interaction(stream, whisper, oww)


def record_until_silence(stream, max_s=14, silence_s=.7):
    chunks, quiet, started = [], 0, False
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


def handle_interaction(stream, whisper, oww):
    _ding()
    set_state("listening")
    audio = record_until_silence(stream)
    set_state("thinking")
    segs, _info = whisper.transcribe(audio, language=CFG["language"], beam_size=2, vad_filter=True)
    text = " ".join(s.text for s in segs).strip()
    if not text:
        set_state("idle")
        return
    print(f"🎙 {text}")
    try:
        answer = think(text)
    except Exception as e:  # noqa: BLE001
        answer = f"Brain hiccup, {CFG['user_title']}: {e}"
    print(f"🎩 {answer}")
    threading.Thread(target=speak, args=(answer,), daemon=True).start()
    oww.reset()


def _ding():
    t = np.linspace(0, .12, int(SR * .12), False)
    tone = (np.sin(2 * np.pi * 880 * t) * np.exp(-t * 18) * .3).astype(np.float32)
    try:
        sd.play(tone, SR)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- orb
ORB_HTML = (APP_DIR / "orb.html").read_text(encoding="utf-8")
ORB_SIZE = 170
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


def _default_home(win):
    screen = webview.screens[0] if webview.screens else None
    sw, sh = (screen.width, screen.height) if screen else (1440, 900)
    return sw - ORB_SIZE - MARGIN, sh - ORB_SIZE - MARGIN


def orb_position_loop(win):
    """Rests bottom-right (or wherever the user last dragged it to), glides
    to screen-center while active, and detects manual drags to remember the
    new resting spot."""
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
            target = (sw // 2 - ORB_SIZE // 2, sh // 2 - ORB_SIZE // 2)
            win.move(*target)
            last_known, moving_until = target, now + .6
        elif mode == "idle" and last_mode != "idle":
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
    threading.Thread(target=audio_loop, daemon=True).start()

    global webview
    import webview
    win = webview.create_window(
        "Jarvis", html=ORB_HTML, js_api=OrbApi(),
        width=ORB_SIZE, height=ORB_SIZE, x=None, y=None,
        frameless=True, on_top=True, transparent=True, resizable=False,
        easy_drag=True)
    webview.start(orb_position_loop, win)  # blocks until the orb window closes


if __name__ == "__main__":
    main()
