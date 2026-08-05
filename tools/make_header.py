#!/usr/bin/env python3
"""assets/portrait.txt + live GitHub stats -> assets/profile-header.svg

    python3 tools/make_header.py

Needs no photo and no dependencies, so CI can run it on a schedule to keep the
numbers current. If the API call fails (rate limit, no network) the last known
values in assets/stats.json are reused, so a bad run can never overwrite the
header with zeroes.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from html import escape
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ART = REPO / "assets" / "portrait.txt"
SVG = REPO / "assets" / "profile-header.svg"
CACHE = REPO / "assets" / "stats.json"

USER = "Adebayodamilola20"

# --- layout -----------------------------------------------------------------
W = 1080
PAD = 40
ART_W = 440                 # the art keeps the .txt aspect; height follows
PANEL_X = 512
KEY_W = 178
ROW_H = 19.5
PANEL_FS = 13

BG, EDGE = "#0d1117", "#30363d"
INK = "#b8d6f0"             # the portrait
NAME, HOST = "#ffa657", "#c9d1d9"
KEY, VAL, RULE = "#58a6ff", "#c9d1d9", "#7ee787"


def fetch() -> dict:
    """Live profile numbers, falling back to the committed cache."""
    hdr = {"User-Agent": "profile-header", "Accept": "application/vnd.github+json"}
    if tok := os.environ.get("GITHUB_TOKEN"):
        hdr["Authorization"] = f"Bearer {tok}"

    def api(path):
        req = urllib.request.Request(f"https://api.github.com/{path}", headers=hdr)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    try:
        u = api(f"users/{USER}")
        repos = api(f"users/{USER}/repos?per_page=100&type=owner")
        langs: dict[str, int] = {}
        for r in repos:
            if r.get("language"):
                langs[r["language"]] = langs.get(r["language"], 0) + 1
        stats = {
            "repos": u["public_repos"],
            "followers": u["followers"],
            "following": u["following"],
            "stars": sum(r.get("stargazers_count", 0) for r in repos),
            "top_language": max(langs, key=langs.get) if langs else "TypeScript",
        }
        CACHE.write_text(json.dumps(stats, indent=2) + "\n")
        return stats
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError) as e:
        if CACHE.exists():
            print(f"stats fetch failed ({e}); reusing {CACHE.name}")
            return json.loads(CACHE.read_text())
        raise


def rows(s: dict) -> list[tuple[str, str] | None | str]:
    """None = blank line, str = section rule, tuple = key/value row."""
    return [
        ("OS:", "macOS · Windows · Linux"),
        ("Coding since:", "2022"),
        ("Host:", "Stephen Tech Studio"),
        ("Kernel:", "AI Engineer · Full Stack Developer"),
        ("IDE:", "VS Code, Android Studio, Xcode"),
        None,
        ("Languages.Programming:", "TypeScript, Python, Dart, JavaScript, C#"),
        ("Languages.Frameworks:", "React, Next.js, Flutter, Node.js, FastAPI"),
        ("Languages.Real:", "English"),
        None,
        ("Focus.AI:", "Autonomous agents, multi-agent systems"),
        ("Focus.Product:", "RELIC, Patrol Security Ecosystem"),
        None,
        "Contact",
        ("Email:", "adebayodamilola2007@gmail.com"),
        ("Website:", "stephentechstudio.vercel.app"),
        ("GitHub:", USER),
        None,
        "GitHub Stats",
        ("Repos:", str(s["repos"])),
        ("Stars:", str(s["stars"])),
        ("Followers:", f"{s['followers']}   ·   Following: {s['following']}"),
        ("Top Language:", s["top_language"]),
    ]


def build() -> str:
    art = ART.read_text().rstrip("\n").split("\n")
    cols = max(len(l) for l in art)

    cw = ART_W / cols                    # monospace advance
    fs = cw / 0.6                        # ui-monospace advance is ~0.6em
    lh = cw / 0.5                        # CHAR_ASPECT from make_portrait
    art_h = lh * len(art)

    body = rows(fetch())
    panel_h = ROW_H * len(body)
    H = round(max(art_h, panel_h) + PAD * 2)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Adebayo Stephen — ASCII portrait and profile summary">',
        '<style>text{font-family:ui-monospace,SFMono-Regular,"SF Mono",Menlo,'
        'Consolas,"Liberation Mono","Courier New",monospace;white-space:pre}</style>',
        f'<rect width="{W}" height="{H}" rx="12" fill="{BG}"/>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" '
        f'fill="none" stroke="{EDGE}"/>',
    ]

    # portrait
    y = (H - art_h) / 2 + lh * 0.8
    out.append(f'<g fill="{INK}" font-size="{fs:.2f}">')
    for line in art:
        if line.strip():
            out.append(f'<text x="{PAD}" y="{y:.1f}">{escape(line)}</text>')
        y += lh
    out.append("</g>")

    # info panel
    y = (H - panel_h) / 2 + ROW_H * 0.8
    out.append(f'<g font-size="{PANEL_FS}">')
    out.append(f'<text x="{PANEL_X}" y="{y:.1f}" font-weight="bold">'
               f'<tspan fill="{NAME}">stephen</tspan>'
               f'<tspan fill="{HOST}">@github</tspan></text>')
    out.append(f'<line x1="{PANEL_X}" y1="{y + 7:.1f}" x2="{W - PAD}" '
               f'y2="{y + 7:.1f}" stroke="{EDGE}"/>')
    y += ROW_H * 1.6

    for row in body:
        if row is None:
            y += ROW_H * 0.6
            continue
        if isinstance(row, str):
            out.append(f'<text x="{PANEL_X}" y="{y:.1f}" fill="{RULE}" '
                       f'font-weight="bold">— {escape(row)}</text>')
            y += ROW_H
            continue
        k, v = row
        out.append(f'<text x="{PANEL_X}" y="{y:.1f}" fill="{KEY}">{escape(k)}</text>')
        out.append(f'<text x="{PANEL_X + KEY_W}" y="{y:.1f}" fill="{VAL}">'
                   f'{escape(v)}</text>')
        y += ROW_H
    out.append("</g></svg>")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    svg = build()
    SVG.write_text(svg)
    print(f"wrote {SVG}  {len(svg)} bytes")
