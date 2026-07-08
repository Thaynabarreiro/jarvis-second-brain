#!/usr/bin/env python3
"""Lightweight standby listener.

Solves a real limitation: Jarvis can only hear "Hey Jarvis" or claps while
the full app is running - if you force-quit it entirely, nothing is left
listening. This tiny sentinel is the fix: it holds only the mic + the wake
word model (no Whisper, no TTS, no orb window - cheap enough to run
continuously), and the moment it hears a wake trigger while the full app is
NOT running, it launches jarvis.py and gets out of the way.

Meant to run via a LaunchAgent/scheduled task with auto-restart, so once it
exits (after launching Jarvis, or because Jarvis is already up) the OS
brings it back - it naturally toggles standby <-> stepped-aside forever.
"""
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

APP_DIR = Path(__file__).resolve().parent
JARVIS_HOME = Path.home() / ".jarvis"
PID_FILE = JARVIS_HOME / "jarvis.pid"
CONFIG_PATH = JARVIS_HOME / "config.json"
VENV_PYTHON = JARVIS_HOME / "venv" / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")

SR = 16000
FRAME = 1280


def jarvis_alive():
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
    except ValueError:
        return False
    try:
        if platform.system() == "Windows":
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                               capture_output=True, text=True, timeout=5)
            return str(pid) in r.stdout
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def launch_jarvis():
    subprocess.Popen([str(VENV_PYTHON), str(APP_DIR / "jarvis.py")], cwd=str(APP_DIR),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=(platform.system() != "Windows"))


def listen_until_wake(oww):
    """Holds one continuous mic session while Jarvis is down (reopening the
    device every few seconds is what caused CoreAudio hangs before). Returns
    True on a wake trigger, False if Jarvis came up some other way."""
    clap_t, level = 0.0, 0.0
    with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=FRAME) as stream:
        while True:
            if jarvis_alive():
                return False
            frame, _ = stream.read(FRAME)
            mono = frame[:, 0]
            peak = np.abs(mono).max() / 32768.0
            level = level * .97 + peak * .03
            if peak > max(.35, level * 4):
                now = time.time()
                if .1 < now - clap_t < .8:
                    return True
                clap_t = now
            elif oww.predict(mono)["hey_jarvis"] > .4:
                return True


def main():
    from openwakeword.model import Model
    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    print("(standby listener active - say 'Hey Jarvis' or clap twice to wake the full app)")

    # One long-lived process: idle-poll (mic released) while Jarvis is up,
    # listen (mic held) while it's down. Never exits, so launchd doesn't
    # churn through restart cycles every few seconds.
    while True:
        if jarvis_alive():
            time.sleep(5)
            continue
        if listen_until_wake(oww):
            print("Wake trigger heard - launching Jarvis.")
            launch_jarvis()
            time.sleep(15)  # give the full app time to claim the pid lock


if __name__ == "__main__":
    main()
