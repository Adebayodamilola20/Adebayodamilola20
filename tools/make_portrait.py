#!/usr/bin/env python3
"""Photo -> ASCII portrait, written to assets/portrait.txt.

Run this only when the source photo changes:

    python3 tools/make_portrait.py ~/Pictures/profile-source.jpg

The header build (tools/make_header.py) reads the .txt, so it never needs the
photo. That keeps the source image out of a public repo and lets CI refresh
the stats without it.

Three things had to be right before this looked like a person at all:

1. Mask to the silhouette FIRST. The tone range has to be measured on the head
   alone. Measured on the whole frame, the wall (~207) owns the bright end and
   the face (68-100) collapses into one flat blob. Masking to an ellipse is not
   enough -- an ellipse still contains wall.
2. Dense glyph = BRIGHT pixel. Light text on a dark page means more ink emits
   more light, so mapping dark pixels to dense glyphs renders a photographic
   negative. This is the mistake that made the first version unrecognisable.
3. Enough columns. Evenly lit faces need resolution: at 88 columns the eye band
   is 4 rows and the glasses turn to mush. 150 is where the frames read.
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

REPO = Path(__file__).resolve().parent.parent
DEST = REPO / "assets" / "portrait.txt"

RAMP = " .-+#@"          # index 0 = blank = darkest pixel
CHAR_ASPECT = 0.5        # glyph width / height
COLS = 150
CROP = (375, 690, 800, 1290)   # head + neck: no shirt, no door, no ceiling
BG_CUT = 150.0           # wall reads ~207, shirt ~163, face 68-100
CONTRAST = 2.0
DETAIL = 0.40
FLOOR = 0.10             # dark hair on a dark page needs a floor, or the
FADE = 7                 # silhouette disappears entirely


def _box(a, r, axis):
    r = max(1, int(r))
    pad = [(0, 0), (0, 0)]
    pad[axis] = (r, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis)
    c = np.concatenate([np.zeros_like(np.take(c, [0], axis=axis)), c], axis=axis)
    n = a.shape[axis]
    return (np.take(c, range(2 * r + 1, 2 * r + 1 + n), axis=axis)
            - np.take(c, range(0, n), axis=axis)) / (2 * r + 1)


def _blur(a, r):
    """Three box passes ~= a Gaussian. PIL cannot blur float images."""
    for _ in range(3):
        a = _box(_box(a, r / 2, 0), r / 2, 1)
    return a


def _flood(m, seeds, want):
    h, w = m.shape
    seen = np.zeros_like(m)
    q = deque()
    for s in seeds:
        if m[s] == want and not seen[s]:
            seen[s] = True
            q.append(s)
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and m[ny, nx] == want and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return seen


def silhouette(im):
    """Largest dark blob through the middle, with interior holes filled."""
    g = np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(3)), np.float32)
    m = g < BG_CUT
    h, w = m.shape
    head = _flood(m, [(int(h * 0.40), int(w * 0.50))], True)
    border = [(y, x) for y in range(h) for x in (0, w - 1)]
    border += [(y, x) for x in range(w) for y in (0, h - 1)]
    return ~_flood(head, border, False)      # lens glare belongs to the head


def levels(im, mask):
    a = np.asarray(im.convert("L").filter(ImageFilter.MedianFilter(3)), np.float32)
    lo, hi = np.percentile(a[mask], 12), np.percentile(a[mask], 88)
    v = np.clip((a - lo) / max(hi - lo, 1.0), 0, 1)
    v = np.clip(0.5 + CONTRAST * (v - 0.5), 0, 1)

    r = a.shape[1] * 0.035
    d = a - _blur(a, r)
    s = np.sqrt(np.maximum(_blur(d * d, r), 1e-3))
    return np.clip(v + DETAIL * np.clip(d / (s + 5.0), -2, 2) / 2, 0, 1)


def build(src: Path, cols: int = COLS, crop=CROP) -> list[str]:
    im = Image.open(src).convert("RGB").crop(crop)
    w, h = im.size
    mask = silhouette(im)
    v = levels(im, mask)

    rows = int(round(cols * CHAR_ASPECT * h / w))
    sm = np.asarray(Image.fromarray((v * 255).astype(np.uint8))
                    .resize((cols, rows), Image.LANCZOS), np.float32) / 255.0
    cov = np.asarray(Image.fromarray((mask * 255).astype(np.uint8))
                     .resize((cols, rows), Image.LANCZOS), np.float32) / 255.0

    edge = np.clip(cov * 2 - 1, 0, 1)
    fade = np.ones(rows, np.float32)
    fade[-FADE:] = np.linspace(1, 0, FADE)
    sm = np.where(cov > 0.45, (FLOOR + (1 - FLOOR) * sm) * edge * fade[:, None], 0.0)

    idx = np.clip((sm * (len(RAMP) - 1)).round().astype(int), 0, len(RAMP) - 1)

    ink = idx > 1                       # lone marks read as dirt, not form
    pad = np.pad(ink, 1)
    n = sum(pad[1 + dy:1 + dy + rows, 1 + dx:1 + dx + cols]
            for dy in (-1, 0, 1) for dx in (-1, 0, 1)) - ink
    idx[ink & (n <= 1)] = 0

    lines = ["".join(RAMP[i] for i in row).rstrip() for row in idx]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    trim = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    return [l[trim:] for l in lines]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1]).expanduser()
    if not src.exists():
        print(f"no such photo: {src}")
        return 1
    lines = build(src, int(sys.argv[2]) if len(sys.argv) > 2 else COLS)
    DEST.write_text("\n".join(lines) + "\n")
    print(f"wrote {DEST}  {max(len(l) for l in lines)}x{len(lines)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
