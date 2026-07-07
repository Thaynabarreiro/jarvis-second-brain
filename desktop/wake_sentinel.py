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


def main():
    from openwakeword.model import Model
    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
    print("(standby listener active - say 'Hey Jarvis' or clap twice to wake the full app)")

    if jarvis_alive():
        print("Jarvis is already running - standby listener stepping aside.")
        return

    clap_t, level = 0.0, 0.0
    # One continuous mic session for as long as Jarvis is down - reopening the
    # device every few seconds just to poll a file is what caused it to hang
    # on some machines, so we check jarvis_alive() once per frame instead.
    with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=FRAME) as stream:
        while True:
            if jarvis_alive():
                print("Jarvis is already running - standby listener stepping aside.")
                return
            frame, _ = stream.read(FRAME)
            mono = frame[:, 0]
            peak = np.abs(mono).max() / 32768.0
            level = level * .97 + peak * .03
            woke = False
            if peak > max(.35, level * 4):
                now = time.time()
                if .1 < now - clap_t < .8:
                    woke = True
                else:
                    clap_t = now
            elif oww.predict(mono)["hey_jarvis"] > .4:
                woke = True
            if woke:
                print("Wake trigger heard - launching Jarvis.")
                launch_jarvis()
                return


if __name__ == "__main__":
    main()
