#!/usr/bin/env python3
"""
Build script for THE RECKONER — a HyperCard-style history of computation.

Workflow (the modular part):
  1. Edit history-of-computation-master-list.md  (add/change cards)
  2. Run:  python3 build.py
  3. Open index.html

The markdown is the single source of truth. Eras (## Era N — ...) become
timeline stacks; Threads (### Thread X — ...) become theme stacks; every
bullet becomes a card. Bold "**Xn. Title**" lines become chapter labels.
"""
import json, re, sys, pathlib

SRC = pathlib.Path("history-of-computation-master-list.md")
TPL = pathlib.Path("template.html")
OUT_HTML = pathlib.Path("../read/index.html")
THEME    = pathlib.Path("../theme.css")     # shared with the other half
OUT_JSON = pathlib.Path("cards.json")

ERA_RE = re.compile(r"^## Era (\d+) — (.+?)\s*\((.+)\)\s*$")
THREAD_RE = re.compile(r"^### Thread ([A-Z]) — (.+?)\s*$")
CHAPTER_RE = re.compile(r"^\*\*(.+?)\*\*:?\s*$")
BULLET_RE = re.compile(r"^- (.+)$")
HEAD_RE = re.compile(r"^\*\*(.+?)\*\*(.*)$", re.S)

def parse_bullet(text, chapter):
    """Turn one '- ...' line into a card dict."""
    m = HEAD_RE.match(text)
    if m:
        head, rest = m.group(1).strip(), m.group(2)
        # optional suffix before the first colon, e.g. " (Eswatini/South Africa)"
        date, title = "", head
        if " — " in head:
            maybe_date, maybe_title = head.split(" — ", 1)
            # treat as date only if it smells like one (digits or 'c.' or 'Today')
            if re.search(r"\d|Today|c\.", maybe_date):
                date, title = maybe_date.strip(), maybe_title.strip()
        body = rest.lstrip()
        if body.startswith("("):
            close = body.find(")")
            if close != -1 and close < 60:
                title += " " + body[: close + 1]
                body = body[close + 1 :]
        body = body.lstrip()
        if body.startswith(":"):
            body = body[1:].strip()
        if not body:
            body = title
    else:
        date = ""
        if ":" in text and text.index(":") < 80:
            title, body = text.split(":", 1)
            title, body = title.strip(), body.strip()
        else:
            title = text[:70].rstrip() + ("…" if len(text) > 70 else "")
            body = text
        title = re.sub(r"[*_]", "", title)
    card = {"t": title, "b": body}
    if date:
        card["d"] = date
    if chapter:
        card["ch"] = chapter
    return card

def parse(md_text):
    stacks, cur, chapter = [], None, ""
    for raw in md_text.splitlines():
        line = raw.rstrip()
        if not line or line == "---":
            continue
        m = ERA_RE.match(line)
        if m:
            cur = {"id": f"era-{m.group(1)}", "kind": "era",
                   "title": f"Era {m.group(1)}: {m.group(2)}",
                   "sub": m.group(3), "cards": []}
            stacks.append(cur); chapter = ""
            continue
        m = THREAD_RE.match(line)
        if m:
            title = m.group(2)
            sub = ""
            pm = re.match(r"^(.*?)\s*\((.+)\)\s*$", title)
            if pm and len(pm.group(2)) > 8:
                title, sub = pm.group(1), pm.group(2)
            cur = {"id": f"thread-{m.group(1)}", "kind": "thread",
                   "title": f"Thread {m.group(1)}: {title.strip().strip(chr(34))}",
                   "sub": sub, "cards": []}
            stacks.append(cur); chapter = ""
            continue
        if line.startswith("## "):          # Open Questions etc. — stop collecting
            cur = None
            continue
        if cur is None or line.startswith("#"):
            continue
        m = CHAPTER_RE.match(line)
        if m:
            chapter = re.sub(r"^[A-Z]\d+\.\s*", "", m.group(1)).rstrip(":")
            continue
        m = BULLET_RE.match(line)
        if m:
            cur["cards"].append(parse_bullet(m.group(1), chapter))
            continue
        # plain prose paragraph inside a thread (Threads B, C, D, G)
        cur["cards"].append({"t": "Overview", "b": line, **({"ch": chapter} if chapter else {})})
    return [s for s in stacks if s["cards"]]

def main():
    md = SRC.read_text(encoding="utf-8")
    stacks = parse(md)
    n_cards = sum(len(s["cards"]) for s in stacks)
    print(f"Parsed {len(stacks)} stacks, {n_cards} cards:")
    for s in stacks:
        print(f"  {s['id']:<10} {len(s['cards']):>3} cards   {s['title'][:60]}")
    data = json.dumps({"stacks": stacks}, ensure_ascii=False)
    data = data.replace("</", "<\\/")  # keep </script> impossible inside the JSON
    OUT_JSON.write_text(json.dumps({"stacks": stacks}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    theme = THEME.read_text(encoding="utf-8") if THEME.exists() else ""
    if not theme:
        print("  ! theme.css not found — the page will be unstyled")
    html = (TPL.read_text(encoding="utf-8")
              .replace("/*__THEME__*/", theme)
              .replace("/*__DATA__*/null", data))
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_HTML} ({OUT_HTML.stat().st_size//1024} KB) and {OUT_JSON}")

if __name__ == "__main__":
    sys.exit(main())
