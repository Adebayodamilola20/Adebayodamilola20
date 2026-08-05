#!/usr/bin/env python3
"""Two 900x900 avatar candidates -> ~/Downloads.

    python3 tools/make_avatar.py ~/Pictures/profile-source.jpg

GitHub has no API for the profile picture, so this only prepares the files.
Upload one by hand at github.com/settings/profile.

Sized for the circular crop: the head sits inside the inscribed circle, so
nothing important is clipped.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_portrait import CROP as HEAD_CROP, build  # noqa: E402

DL = Path.home() / "Downloads"
SIZE = 900
BG, INK = "#0d1117", "#b8d6f0"
FONT = "/System/Library/Fonts/Menlo.ttc"
# A square crop either clips the chin or drags the dark doorframe into the
# silhouette flood, so reuse the header crop and centre it instead.
CROP = HEAD_CROP


def photo_avatar(src: Path) -> Path:
    im = Image.open(src).convert("RGB").crop(CROP)
    s = min(im.size)
    im = im.crop(((im.width - s) // 2, (im.height - s) // 2,
                  (im.width + s) // 2, (im.height + s) // 2))
    out = DL / "avatar_photo.png"
    im.resize((SIZE, SIZE), Image.LANCZOS).save(out)
    return out


def ascii_avatar(src: Path, cols: int = 70) -> Path:
    lines = build(src, cols, CROP)   # square crop, not the header's tall one
    im = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(im)

    # fit the block inside the circle GitHub crops to (~0.92 of the square)
    fs = 4
    while True:
        f = ImageFont.truetype(FONT, fs + 1)
        cw = f.getlength("M")
        if cw * cols > SIZE * 0.88 or (cw / 0.5) * len(lines) > SIZE * 0.88:
            break
        fs += 1
    f = ImageFont.truetype(FONT, fs)
    cw = f.getlength("M")
    lh = cw / 0.5
    x0 = (SIZE - cw * cols) / 2
    y0 = (SIZE - lh * len(lines)) / 2
    for i, line in enumerate(lines):
        d.text((x0, y0 + i * lh), line, font=f, fill=INK)

    out = DL / "avatar_ascii.png"
    im.save(out)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    photo = Path(sys.argv[1]).expanduser()
    print("wrote", photo_avatar(photo))
    print("wrote", ascii_avatar(photo))
