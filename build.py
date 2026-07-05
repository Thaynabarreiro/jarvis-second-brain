#!/usr/bin/env python3
"""Escaneia as notas .md e gera viewer/graph-data.js para a galáxia 3D."""
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
_cfg = json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))
NOTES_DIR = _cfg.get("notes_dir") or os.path.join(BASE, "notes")
SKIP_DIRS = {".obsidian", ".smart-env", ".trash", ".git", "node_modules"}
OUT = os.path.join(BASE, "viewer", "graph-data.js")


def scan():
    nodes = []
    for root, dirs, files in os.walk(NOTES_DIR):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            path = os.path.join(root, f)
            text = open(path, encoding="utf-8", errors="ignore").read()
            label = os.path.splitext(f)[0]
            group = os.path.relpath(root, NOTES_DIR)
            if group == ".":
                group = "Raiz"
            body = re.sub(r"^#.*$", "", text, flags=re.M).strip()
            nodes.append({
                "label": label,
                "group": group,
                "excerpt": body[:700],
                "path": os.path.relpath(path, NOTES_DIR),
                "text": text.lower(),
                "wikilinks": [w.strip().lower() for w in re.findall(r"\[\[([^\]]+)\]\]", text)],
            })

    links = []
    for i, a in enumerate(nodes):
        for j, b in enumerate(nodes):
            if i >= j:
                continue
            a_title, b_title = a["label"].lower(), b["label"].lower()
            linked = (
                b_title in a["text"] or a_title in b["text"]
                or b_title in a["wikilinks"] or a_title in b["wikilinks"]
                or set(a["wikilinks"]) & set(b["wikilinks"])
            )
            if linked:
                links.append({"source": i, "target": j})

    # id numérico = posição no array (features posteriores dependem disso)
    for i, n in enumerate(nodes):
        n["id"] = i
        del n["text"], n["wikilinks"]

    return {"nodes": nodes, "links": links}


if __name__ == "__main__":
    graph = scan()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("const GRAPH = " + json.dumps(graph, ensure_ascii=False) + ";\n")
    print(f"{len(graph['nodes'])} notas, {len(graph['links'])} conexões -> {OUT}")
