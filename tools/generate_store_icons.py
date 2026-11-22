#!/usr/bin/env python3
"""Draws placeholder store icons for every icon the shop catalog names.

Run from the repository root (needs Pillow and the DejaVu/Liberation fonts):

    python3 tools/generate_store_icons.py [--force]

Writes store-images/64/<name>.png (products, 64x64) and store-images/13/<name>.png
(categories, 13x13), which the account service serves at /images/store/. Existing
files are kept unless --force is given, so real icons dropped into those folders
are never overwritten.
"""

import colorsys
import glob
from pathlib import Path
import re
import sys
import zlib

from PIL import Image, ImageDraw, ImageFont

CATALOG = "data/modules/scripts/gamestore/catalog/*.lua"
OUTPUT = Path("store-images")
FONT = "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf"


def icon_names():
    names = set()
    for path in glob.glob(CATALOG):
        names |= set(re.findall(r'"([A-Za-z0-9_.-]+\.png)"', Path(path).read_text(encoding="utf-8")))
    return sorted(names)


def label(name):
    text = re.sub(r"^(Product|Category)_", "", name[:-4]).replace("_", " ")
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z][a-z])", " ", text).strip()


def colours(name):
    hue = (zlib.crc32(name.encode()) % 360) / 360
    dark = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.55, 0.38))
    light = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.45, 0.62))
    return dark, light


def wrap(draw, words, font, width):
    lines, line = [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line]


def product(name):
    dark, light = colours(name)
    image = Image.new("RGB", (64, 64), dark)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 63, 63), outline=light)
    draw.rectangle((2, 2, 61, 61), outline=tuple(c * 2 // 3 for c in light))
    words = label(name).split()
    for size in range(13, 6, -1):
        font = ImageFont.truetype(FONT, size)
        lines = wrap(draw, words, font, 56)
        height = len(lines) * (size + 1)
        if height <= 56 and all(draw.textlength(line, font=font) <= 58 for line in lines):
            break
    top = (64 - height) // 2
    for number, line in enumerate(lines):
        draw.text((32, top + number * (size + 1)), line, font=font, fill=(245, 236, 210), anchor="ma")
    return image


def category(name):
    dark, light = colours(name)
    image = Image.new("RGB", (13, 13), dark)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 12, 12), outline=light)
    letter = (re.sub(r"^Category_", "", name[:-4]) or "?")[0].upper()
    draw.text((6.5, 6.5), letter, font=ImageFont.truetype(FONT, 10), fill=(245, 236, 210), anchor="mm")
    return image


def main():
    force = "--force" in sys.argv[1:]
    written = 0
    for name in icon_names():
        folder, draw = ("13", category) if name.startswith("Category_") else ("64", product)
        target = OUTPUT / folder / name
        if target.exists() and not force:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        draw(name).save(target, optimize=True)
        written += 1
    print(f"{written} icons written to {OUTPUT}/ ({len(list(OUTPUT.glob('*/*.png')))} in total)")


if __name__ == "__main__":
    main()
