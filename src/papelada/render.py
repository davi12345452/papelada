"""Minimal vertical-flow document renderer on top of Pillow.

Layouts describe a document as a list of blocks; a Style decides how they look.

Blocks:
    ("title", text)          ("subtitle", text)     ("amount", text)
    ("section", text)        ("field", label, value)
    ("note", text)           ("rule",)              ("gap", pixels)
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# First existing path wins. macOS paths first, then common Linux paths.
FONT_CANDIDATES: dict[str, list[tuple[str, int]]] = {
    "sans": [
        ("/System/Library/Fonts/Supplemental/Arial.ttf", 0),
        ("/System/Library/Fonts/Helvetica.ttc", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0),
    ],
    "sans_bold": [
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0),
        ("/System/Library/Fonts/Helvetica.ttc", 1),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ],
    "mono": [
        ("/System/Library/Fonts/Supplemental/Courier New.ttf", 0),
        ("/System/Library/Fonts/Menlo.ttc", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
    ],
    "mono_bold": [
        ("/System/Library/Fonts/Supplemental/Courier New Bold.ttf", 0),
        ("/System/Library/Fonts/Menlo.ttc", 1),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 0),
    ],
}


@lru_cache(maxsize=None)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path, index in FONT_CANDIDATES[kind]:
        if Path(path).exists():
            return ImageFont.truetype(path, size, index=index)
    raise FileNotFoundError(f"No font found for {kind!r}; add a path to FONT_CANDIDATES")


@dataclass(frozen=True)
class Style:
    width: int
    family: str = "sans"  # "sans" | "mono"
    margin: int = 40
    bg: str = "#ffffff"
    fg: str = "#111111"
    muted: str = "#6b6b6b"
    accent: str = "#333333"
    body_size: int = 24
    label_size: int = 19
    title_size: int = 30
    amount_size: int = 52
    field_mode: str = "stacked"  # "stacked" | "inline"
    align_title: str = "left"  # "left" | "center"
    header_band: bool = False
    dashed_rules: bool = False
    line_gap: int = 8


def _wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> list[str]:
    """Greedy word wrap; words wider than the line (emails, UUIDs) break by character."""
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=fnt) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = ""
        for char in word:
            if draw.textlength(current + char, font=fnt) > max_width and current:
                lines.append(current)
                current = ""
            current += char
    if current:
        lines.append(current)
    return lines or [""]


def _scaled(style: Style, scale: int) -> Style:
    sizes = {
        name: getattr(style, name) * scale
        for name in ("width", "margin", "body_size", "label_size", "title_size", "amount_size", "line_gap")
    }
    return replace(style, **sizes)


def render(blocks: list[tuple], style: Style, scale: int = 2) -> Image.Image:
    """Layouts are written at 1x; the default 2x matches phone screenshots and 200 DPI scans."""
    regular = "mono" if style.family == "mono" else "sans"
    bold = f"{regular}_bold"
    s = _scaled(style, scale)
    content_width = s.width - 2 * s.margin

    img = Image.new("RGB", (s.width, 6000), s.bg)
    draw = ImageDraw.Draw(img)
    y = s.margin

    def text_line(text: str, fnt, fill: str, align: str = "left") -> None:
        nonlocal y
        width = draw.textlength(text, font=fnt)
        x = {"left": s.margin, "center": (s.width - width) / 2, "right": s.width - s.margin - width}[align]
        draw.text((x, y), text, font=fnt, fill=fill)
        y += fnt.size + s.line_gap

    def rule() -> None:
        nonlocal y
        y += s.line_gap
        if s.dashed_rules:
            for x in range(s.margin, s.width - s.margin, 14):
                draw.line([(x, y), (min(x + 7, s.width - s.margin), y)], fill=s.muted, width=2)
        else:
            draw.line([(s.margin, y), (s.width - s.margin, y)], fill="#d9d9d9", width=2)
        y += s.line_gap * 2

    for i, block in enumerate(blocks):
        kind = block[0]
        if kind == "title":
            fnt = font(bold, s.title_size)
            if s.header_band and i == 0:
                band = int(s.title_size * 2.8)
                draw.rectangle([0, 0, s.width, band], fill=s.accent)
                y = (band - s.title_size) // 2
                text_line(block[1], fnt, "#ffffff", s.align_title)
                y = band + s.margin // 2
            else:
                text_line(block[1], fnt, s.fg, s.align_title)
        elif kind == "subtitle":
            for line in _wrap(draw, block[1], font(regular, s.label_size), content_width):
                text_line(line, font(regular, s.label_size), s.muted, s.align_title)
        elif kind == "amount":
            text_line(block[1], font(bold, s.amount_size), s.fg, s.align_title)
            y += s.line_gap
        elif kind == "section":
            y += s.line_gap * 2
            text_line(block[1], font(bold, s.label_size + 2), s.accent)
        elif kind == "field":
            label, value = block[1], block[2]
            label_font, value_font = font(regular, s.label_size), font(regular, s.body_size)
            if s.field_mode == "stacked":
                text_line(label, label_font, s.muted)
                for line in _wrap(draw, value, value_font, content_width):
                    text_line(line, value_font, s.fg)
                y += s.line_gap
            else:
                label_width = draw.textlength(label, font=label_font)
                room = content_width - label_width - 24
                draw.text((s.margin, y + (s.body_size - s.label_size)), label, font=label_font, fill=s.muted)
                if draw.textlength(value, font=value_font) <= room:
                    text_line(value, value_font, s.fg, "right")
                else:
                    y += s.body_size + s.line_gap
                    for line in _wrap(draw, value, value_font, content_width):
                        text_line(line, value_font, s.fg, "right")
        elif kind == "note":
            for line in _wrap(draw, block[1], font(regular, s.label_size - 2), content_width):
                text_line(line, font(regular, s.label_size - 2), s.muted, s.align_title)
        elif kind == "rule":
            rule()
        elif kind == "gap":
            y += block[1]
        else:
            raise ValueError(f"Unknown block kind: {kind}")

    return img.crop((0, 0, s.width, y + s.margin))
