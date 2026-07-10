"""Study-mode backend: two markdown study tracks (AI Engineering, French),
progress tracking, and lesson rendering for the study screen.

The markdown plan files are read-only source material - progress lives
exclusively in ~/.jarvis/study_progress.json. Paths contain spaces, colons
and accents (iCloud Drive), so everything goes through pathlib untouched.
"""
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

JARVIS_HOME = Path.home() / ".jarvis"
PROGRESS_PATH = JARVIS_HOME / "study_progress.json"

_RESOURCES = Path.home() / ("Library/Mobile Documents/com~apple~CloudDocs/"
                            "30-39 : RECURSOS (Estudos, referências e interesses)")

TRACKS = {
    "ai": {
        "name": "AI Engineering",
        "todo_prefix": "IA",
        "total": 10,
        "root": _RESOURCES / "31_MBA & Estudos/05 - AI ENGINEERING/PLANO-TEORIA-20H",
        # sessions live inside "Fase N - ..." subfolders as Sessao-NN.md,
        # globally numbered 01-10 across the phases
        "glob": "Fase */Sessao-*.md",
        "number_re": re.compile(r"Sessao-(\d+)\.md$", re.I),
    },
    "frances": {
        "name": "Francês B1→C1",
        "todo_prefix": "Francês",
        "total": 20,
        "root": _RESOURCES / "32_Francês/04 - Francês 20hrs",
        "glob": "sessoes/sessao_*.md",
        "number_re": re.compile(r"sessao_(\d+)\.md$", re.I),
    },
}


def read_icloud_text(path):
    """iCloud Drive may hold a file as a cloud placeholder before first
    access. Normal open() usually triggers the download, but if the file
    is genuinely absent locally, ask brctl to fetch it and retry briefly."""
    path = Path(path)
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except FileNotFoundError:
        placeholder = path.parent / f".{path.name}.icloud"
        if placeholder.exists():
            subprocess.run(["brctl", "download", str(path)], capture_output=True, timeout=10)
            for _ in range(20):
                if path.exists():
                    return path.read_text(encoding="utf-8", errors="ignore")
                time.sleep(0.5)
        raise


# ------------------------------------------------------------------ progress
def _load_progress():
    try:
        return json.loads(PROGRESS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_progress(data):
    PROGRESS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _track_state(progress, track_id):
    return progress.setdefault(track_id, {"completed": [], "total_minutes": 0})


def current_session(track_id):
    """First session number not yet completed (the 'session of the day')."""
    done = {c["n"] for c in _track_state(_load_progress(), track_id)["completed"]}
    total = TRACKS[track_id]["total"]
    for n in range(1, total + 1):
        if n not in done:
            return n
    return None  # track finished


def complete_session(track_id, minutes=0):
    progress = _load_progress()
    state = _track_state(progress, track_id)
    n = current_session(track_id)
    if n is None:
        return None
    state["completed"].append({"n": n, "date": datetime.now().strftime("%Y-%m-%d"),
                               "minutes": int(minutes)})
    if minutes:
        state["total_minutes"] = state.get("total_minutes", 0) + int(minutes)
    _save_progress(progress)
    return n


def log_minutes(track_id, minutes):
    if int(minutes) <= 0:
        return
    progress = _load_progress()
    state = _track_state(progress, track_id)
    state["total_minutes"] = state.get("total_minutes", 0) + int(minutes)
    _save_progress(progress)


# ------------------------------------------------------------------ sessions
def find_session_file(track_id, n):
    track = TRACKS[track_id]
    for path in sorted(track["root"].glob(track["glob"])):
        m = track["number_re"].search(path.name)
        if m and int(m.group(1)) == n:
            return path
    return None


def session_title(track_id, n):
    path = find_session_file(track_id, n)
    if not path:
        return None
    for line in read_icloud_text(path).splitlines():
        if line.startswith("# "):
            # strip emoji/prefix noise like "📝 Sessão 01: ..."
            return line.lstrip("# ").strip()
    return path.stem


def study_summary():
    """Compact per-track status for the home card and voice answers."""
    out = []
    for track_id, track in TRACKS.items():
        n = current_session(track_id)
        title = session_title(track_id, n) if n else None
        out.append({
            "id": track_id,
            "name": track["name"],
            "session": n,
            "total": track["total"],
            "title": title,
            "done": n is None,
        })
    return out


# ------------------------------------------------------------------ rendering
_YT_RE = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})[^\s<>\")]*")
_URL_RE = re.compile(r"(?<![\"'>(])(https?://[^\s<>\")]+)")


def _linkify(html):
    """Turn bare URLs into anchors, and append a clickable YouTube thumbnail
    card after each distinct YouTube link.

    Order matters: thumbnail markers MUST be inserted while the URLs are
    still bare text. Doing it after anchor creation planted the marker
    inside the href attribute (the regex's first hit is the href copy of
    the URL), splitting the tag and rendering broken '">https://...' text
    instead of a link + card."""
    # 1) markers after each distinct YouTube URL (still plain text here)
    seen = set()
    out = []
    pos = 0
    for m in _YT_RE.finditer(html):
        out.append(html[pos:m.end()])
        pos = m.end()
        vid = m.group(1)
        if vid not in seen:
            seen.add(vid)
            out.append(f'<span class="yt-thumb-anchor" data-vid="{vid}"></span>')
    out.append(html[pos:])
    html = "".join(out)

    # 2) now wrap bare URLs in anchors ([^<>"] in the pattern stops the
    #    match cleanly before the marker span)
    def repl(m):
        url = m.group(1)
        return f'<a href="{url}">{url}</a>'
    return _URL_RE.sub(repl, html)


def render_session_html(track_id, n=None):
    """Markdown -> HTML for the lesson pane. Returns dict with title/html."""
    import markdown as md
    if n is None:
        n = current_session(track_id)
    if n is None:
        return {"title": "Trilha concluída 🎉", "html": "<p>Todas as sessões desta trilha foram concluídas.</p>", "session": None}
    path = find_session_file(track_id, n)
    if not path:
        return {"title": f"Sessão {n}", "html": "<p>Arquivo da sessão não encontrado.</p>", "session": n}
    text = read_icloud_text(path)
    html = md.markdown(text, extensions=["tables", "sane_lists", "fenced_code"])
    html = _linkify(html)
    title = session_title(track_id, n) or f"Sessão {n}"
    return {"title": title, "html": html, "session": n,
            "track": TRACKS[track_id]["name"], "track_id": track_id}
