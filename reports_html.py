#!/usr/bin/env python3
"""Build reports/index.html - one self-contained page to read every saved report.

Reads reports/<date>/*.txt|*.md (written by make_report.py) and embeds them in
a single HTML file: dates down the side (newest first), one tab per report.
No server needed - open the file in a browser. Stories (.md) get light
formatting (**bold**, *italic*, headings, paragraphs); briefs (.txt) are shown
as-is in monospace. Persian stories (story_fa*) are laid out right-to-left.

make_report.py runs this after every report; run it by hand after editing or
deleting reports.

Usage:
    python3 reports_html.py                      # reports/ -> reports/index.html
    python3 reports_html.py --reports-dir ~/price-in-reports
"""
import argparse
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATE_DIR = re.compile(r"\d{4}-\d{2}-\d{2}")
STORY_FILE = re.compile(r"brief_(en|fa)\.txt")   # make_report.py's saved reports


def md_to_html(text):
    """Just enough markdown for story output: headings, bold, italic, paragraphs."""
    out, para = [], []

    def inline(s):
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", s)
        return s

    def flush():
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    lines = [l.strip() for l in text.splitlines()]
    is_rule = lambda s: bool(s) and set(s) <= set("=-─")
    for n, s in enumerate(lines):
        if not s or is_rule(s):                     # blank or rule line
            flush()
        elif (0 < n < len(lines) - 1 and is_rule(lines[n - 1])
              and is_rule(lines[n + 1])):           # title inside a ==== banner
            flush()
            out.append(f'<h1 class="title">{inline(s)}</h1>')
        elif s.startswith("▌"):                      # pair header from story.py
            flush()
            out.append(f"<h2>{inline(s.lstrip('▌ '))}</h2>")
        elif m := re.match(r"(#{1,4})\s+(.*)", s):
            flush()
            out.append(f"<h{len(m.group(1)) + 1}>{inline(m.group(2))}</h{len(m.group(1)) + 1}>")
        elif re.fullmatch(r"\*\*[^*]+\*\*", s):      # a line that is only bold = heading
            flush()
            out.append(f"<h3>{inline(s[2:-2])}</h3>")
        else:
            para.append(s)
    flush()
    return "\n".join(out)


def label_for(name):
    stem = os.path.splitext(name)[0]
    kind, _, rest = stem.partition("_")
    lang = {"en": "English", "fa": "فارسی"}
    parts = rest.split("_") if rest else []
    bits = [lang.get(p, p.upper()) for p in parts]
    return f"{kind.capitalize()}{' · ' + ' · '.join(bits) if bits else ''}"


def collect(reports_dir):
    """[{date, files: [{name, label, rtl, html}]}], newest date first."""
    days = []
    for d in sorted(os.listdir(reports_dir), reverse=True):
        path = os.path.join(reports_dir, d)
        if not (DATE_DIR.fullmatch(d) and os.path.isdir(path)):
            continue
        files = []
        # brief first, then stories; English before Persian
        for name in sorted(os.listdir(path), key=lambda n: (not n.startswith("brief"), n)):
            if not name.endswith((".txt", ".md")):
                continue
            text = open(os.path.join(path, name), encoding="utf-8").read()
            # brief_<lang>.txt is story.py output (the saved report): format it
            # like a story. Anything else .txt (e.g. an old rules-only brief.txt)
            # is shown as printed.
            is_story = name.endswith(".md") or STORY_FILE.fullmatch(name)
            body = (md_to_html(text) if is_story
                    else f"<pre>{html.escape(text)}</pre>")
            files.append({"name": name, "label": label_for(name),
                          "rtl": "_fa" in name, "html": body})
        if files:
            days.append({"date": d, "files": files})
    return days


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>price-in reports</title>
<style>
:root {
  --bg: #f7f7f5; --panel: #ffffff; --text: #1d1d1f; --muted: #6e6e73;
  --line: #e3e3e0; --accent: #2f5fd0; --accent-bg: #e8eefb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161618; --panel: #1f1f22; --text: #ececee; --muted: #9a9aa0;
    --line: #2e2e33; --accent: #8fb0ff; --accent-bg: #25304a;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
.wrap { display: flex; min-height: 100vh; }
nav { width: 180px; flex: none; border-right: 1px solid var(--line);
  padding: 20px 12px; position: sticky; top: 0; height: 100vh; overflow-y: auto; }
nav h1 { font-size: 15px; margin: 0 8px 14px; }
nav button { display: block; width: 100%; text-align: left; border: 0;
  background: none; color: var(--text); padding: 7px 10px; border-radius: 6px;
  font: inherit; font-size: 14px; cursor: pointer; font-variant-numeric: tabular-nums; }
nav button:hover { background: var(--line); }
nav button.on { background: var(--accent-bg); color: var(--accent); font-weight: 600; }
main { flex: 1; min-width: 0; padding: 24px 32px 60px; }
.tabs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 18px; }
.tabs button { border: 1px solid var(--line); background: var(--panel); color: var(--text);
  padding: 6px 14px; border-radius: 999px; font: inherit; font-size: 14px; cursor: pointer; }
.tabs button.on { border-color: var(--accent); color: var(--accent); background: var(--accent-bg); }
article { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 24px 28px; max-width: 820px; }
article h2 { font-size: 20px; margin: 28px 0 8px; padding-top: 16px;
  border-top: 1px solid var(--line); }
article h2:first-child { margin-top: 0; padding-top: 0; border-top: 0; }
article h3 { font-size: 16px; margin: 18px 0 6px; }
article h1.title { font-size: 13px; letter-spacing: .08em; color: var(--muted); margin: 0 0 18px; }
article p { margin: 0 0 12px; }
article pre { margin: 0; white-space: pre-wrap; word-break: break-word;
  font: 13px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; }
article[dir=rtl] { font-family: Tahoma, "Vazirmatn", sans-serif; line-height: 1.9; }
.meta { color: var(--muted); font-size: 13px; margin: 0 0 12px; }
.empty { color: var(--muted); }
@media (max-width: 700px) {
  .wrap { display: block; }
  nav { width: auto; height: auto; position: static; border-right: 0;
    border-bottom: 1px solid var(--line); padding: 12px 16px;
    display: flex; gap: 4px; overflow-x: auto; }
  nav h1 { display: none; }
  nav button { width: auto; white-space: nowrap; }
  main { padding: 16px; }
  article { padding: 18px 16px; }
}
</style>
</head>
<body>
<div class="wrap">
  <nav id="dates"><h1>Reports</h1></nav>
  <main>
    <div class="tabs" id="tabs"></div>
    <p class="meta" id="meta"></p>
    <article id="body"></article>
  </main>
</div>
<script>
const DAYS = __DATA__;
const $ = id => document.getElementById(id);
let day = 0, file = 0;

function remember() {
  try { localStorage.setItem("pricein-reports", JSON.stringify({d: DAYS[day].date, f: DAYS[day].files[file].name})); } catch (e) {}
}
function show() {
  document.querySelectorAll("#dates button").forEach((b, i) => b.classList.toggle("on", i === day));
  const d = DAYS[day];
  $("tabs").innerHTML = "";
  d.files.forEach((f, i) => {
    const b = document.createElement("button");
    b.textContent = f.label;
    b.className = i === file ? "on" : "";
    b.onclick = () => { file = i; show(); };
    $("tabs").appendChild(b);
  });
  const f = d.files[file];
  $("meta").textContent = d.date + " · " + f.name;
  $("body").innerHTML = f.html;
  $("body").dir = f.rtl ? "rtl" : "ltr";
  remember();
}
if (!DAYS.length) {
  $("body").innerHTML = '<p class="empty">No reports yet — run <code>python3 make_report.py</code>.</p>';
} else {
  DAYS.forEach((d, i) => {
    const b = document.createElement("button");
    b.textContent = d.date;
    b.onclick = () => { day = i; file = 0; show(); };
    $("dates").appendChild(b);
  });
  try {
    const s = JSON.parse(localStorage.getItem("pricein-reports") || "null");
    if (s) {
      const di = DAYS.findIndex(d => d.date === s.d);
      if (di >= 0) { day = di; file = Math.max(0, DAYS[di].files.findIndex(f => f.name === s.f)); }
    }
  } catch (e) {}
  show();
}
</script>
</body>
</html>
"""


def build(reports_dir):
    days = collect(reports_dir)
    # </ inside embedded JSON would end the <script> early
    data = json.dumps(days, ensure_ascii=False).replace("</", "<\\/")
    out = os.path.join(reports_dir, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(PAGE.replace("__DATA__", data))
    return out, days


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reports-dir", default=os.path.join(HERE, "reports"))
    a = ap.parse_args()
    d = os.path.expanduser(a.reports_dir)
    os.makedirs(d, exist_ok=True)
    out, days = build(d)
    print(f"{sum(len(x['files']) for x in days)} reports over {len(days)} dates -> {out}")


if __name__ == "__main__":
    main()
