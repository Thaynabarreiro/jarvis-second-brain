#!/usr/bin/env python3
"""Servidor do Jarvis: serve viewer/ e expõe /chat e /remember.

Só biblioteca padrão. A API key vive em config.json (fora de viewer/)
e nunca é enviada ao navegador. Se a key ainda for o placeholder,
o /chat cai para `claude -p` (usa sua assinatura do Claude Code).
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler

BASE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(BASE, "viewer")
_cfg = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
NOTES_DIR = _cfg.get("notes_dir") or os.path.join(BASE, "notes")
SKIP_DIRS = {".obsidian", ".smart-env", ".trash", ".git", "node_modules"}
PORT = 4700

HISTORY = []  # histórico curto da sessão (lado servidor)
MAX_HISTORY = 12

SYSTEM_PROMPT = """Você é Jarvis: um mordomo britânico impecavelmente educado, seco e de humor afiado, falando em português do Brasil. Chame a usuária de "senhora" de vez em quando (não em toda frase). Uma tirada genuinamente engraçada vale mais que três frases sem graça.

Regras:
- Responda perguntas sobre as notas em UMA frase espirituosa + os fatos, em 2-3 frases no total. Nunca recite a nota de volta — ela já está na tela.
- Responda APENAS com base nas notas fornecidas. Se as notas não cobrirem o assunto, admita com elegância.
- Papo furado e piadas: responda com graça, sem citar notas.
- Responda SEMPRE em JSON válido: {"answer": "...", "nodes": [ids das notas usadas], "smalltalk": true/false}. Se não usou nenhuma nota, "nodes" fica vazio e "smalltalk" true."""


def load_config():
    with open(os.path.join(BASE, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def load_notes():
    notes = []
    for root, dirs, files in os.walk(NOTES_DIR):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for fn in sorted(files):
            if fn.endswith(".md"):
                text = open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read()
                notes.append({"title": os.path.splitext(fn)[0], "text": text})
    return notes


def score_notes(question, notes):
    words = set(re.findall(r"\w{3,}", question.lower()))
    scored = []
    for i, n in enumerate(notes):
        text = n["text"].lower()
        title = n["title"].lower()
        s = sum(text.count(w) for w in words) + sum(5 for w in words if w in title)
        scored.append((s, i))
    scored.sort(reverse=True)
    return [i for s, i in scored[:6] if s > 0]


def call_anthropic(cfg, messages):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": cfg["model"],
            "max_tokens": 700,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": cfg["api_key"],
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    return data["content"][0]["text"]


def call_claude_cli(messages):
    convo = "\n\n".join(f'[{m["role"]}]\n{m["content"]}' for m in messages)
    out = subprocess.run(
        ["claude", "-p", SYSTEM_PROMPT + "\n\n" + convo],
        capture_output=True, text=True, timeout=180,
    )
    return out.stdout.strip()


def parse_answer(raw, candidates):
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        data = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        data = {}
    answer = data.get("answer") or raw.strip() or "As linhas se cruzaram, senhora. Tente novamente."
    nodes = [n for n in data.get("nodes", []) if isinstance(n, int)]
    if not nodes and not data.get("smalltalk"):
        nodes = candidates[:1]
    return {"answer": answer, "nodes": nodes}


def handle_chat(question):
    notes = load_notes()
    top = score_notes(question, notes)
    context = "\n\n".join(
        f"[NOTA id={i}] {notes[i]['title']}\n{notes[i]['text'][:1500]}" for i in top
    ) or "(nenhuma nota relevante encontrada)"

    HISTORY.append({"role": "user", "content": f"NOTAS RELEVANTES:\n{context}\n\nPERGUNTA: {question}"})
    del HISTORY[:-MAX_HISTORY]

    cfg = load_config()
    if cfg["api_key"].startswith("PUT-YOUR"):
        raw = call_claude_cli(HISTORY)
    else:
        raw = call_anthropic(cfg, HISTORY)
    HISTORY.append({"role": "assistant", "content": raw})
    return parse_answer(raw, top)


def handle_remember(text):
    content = re.sub(r"^(lembre(-se)?( de)?( que)?|remember( that)?)\s*", "", text.strip(), flags=re.I)
    title = " ".join(re.findall(r"\w+", content)[:6]).capitalize() or "Nota capturada"
    cap_dir = os.path.join(NOTES_DIR, "captures")
    os.makedirs(cap_dir, exist_ok=True)
    safe = re.sub(r"[^\w\s-]", "", title).strip()
    path = os.path.join(cap_dir, f"{safe}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n{content}\n")
    # reconstrói o grafo e devolve o novo nó + vizinho mais relacionado
    subprocess.run([sys.executable, os.path.join(BASE, "build.py")], capture_output=True)
    graph_js = open(os.path.join(VIEWER, "graph-data.js"), encoding="utf-8").read()
    graph = json.loads(graph_js[graph_js.index("{"):graph_js.rindex("}") + 1])
    new_id = next(n["id"] for n in graph["nodes"] if n["label"] == safe)
    neighbor = next((l["target"] if l["source"] == new_id else l["source"]
                     for l in graph["links"] if new_id in (l["source"], l["target"])), None)
    return {"node": next(n for n in graph["nodes"] if n["id"] == new_id),
            "graph": graph, "neighbor": neighbor,
            "answer": f"Anotado e arquivado, senhora. “{title}” agora brilha na sua galáxia."}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kw):
        super().__init__(*args, directory=VIEWER, **kw)

    def log_message(self, *a):
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/chat":
                text = payload.get("question", "")
                if re.match(r"^\s*(lembre|remember)", text, re.I):
                    self._json(handle_remember(text))
                else:
                    self._json(handle_chat(text))
            elif self.path == "/remember":
                self._json(handle_remember(payload.get("text", "")))
            else:
                self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            self._json({"answer": f"Um contratempo técnico, senhora: {e}", "nodes": []}, 500)


if __name__ == "__main__":
    print(f"Jarvis de prontidão em http://localhost:{PORT} (abra no Chrome)")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
