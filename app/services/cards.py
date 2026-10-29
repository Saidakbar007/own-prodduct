"""
PNG-карточки для сторис (§10 ТЗ): серия и Reveal, 1080×1920, в стиле
DESIGN.md — генерируются на сервере через Pillow, без браузера и без JS.
Шрифты — те же, что в дизайн-системе (app/static/fonts/, OFL-лицензия).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

CARD_W, CARD_H = 1080, 1920
MARGIN = 88
CARDS_DIR = "cards"

COLOR_BG = (21, 18, 15)
COLOR_GLOW = (255, 182, 72)
COLOR_GLOW_GREEN = (31, 190, 140)
COLOR_TEXT = (245, 239, 228)
COLOR_MUTED = (184, 173, 157)
COLOR_FAINT = (134, 122, 105)
COLOR_ACCENT = (255, 182, 72)
COLOR_ACCENT_STRONG = (255, 203, 117)
COLOR_DONE = (61, 203, 131)
COLOR_DONE_SOFT = (41, 61, 51)
COLOR_SURFACE_RAISED = (42, 36, 29)
COLOR_BORDER = (56, 50, 42)

FONTS_DIR = Path(__file__).parent.parent / "static" / "fonts"
_FONT_CACHE: dict[tuple[str, int, str], ImageFont.FreeTypeFont] = {}


def _font(family: str, size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    key = (family, size, weight)
    if key not in _FONT_CACHE:
        filename = "Unbounded-Bold.ttf" if family == "display" else "GolosText-Regular.ttf"
        font = ImageFont.truetype(str(FONTS_DIR / filename), size)
        try:
            font.set_variation_by_name(weight)
        except OSError:
            pass
        _FONT_CACHE[key] = font
    return _FONT_CACHE[key]


def _vertical_glow(height_ratio: float, color: tuple[int, int, int], strength: float = 0.4):
    """Тёплое свечение сверху карточки (как radial-gradient в CSS), только
    по вертикали — дёшево и достаточно похоже на /design/story."""
    grad = Image.new("L", (1, CARD_H))
    span = CARD_H * height_ratio
    for y in range(CARD_H):
        t = max(0.0, 1 - y / span) if span else 0.0
        grad.putpixel((0, y), int(255 * t * strength))
    grad = grad.resize((CARD_W, CARD_H))
    layer = Image.new("RGB", (CARD_W, CARD_H), color)
    return layer, grad


def _background() -> Image.Image:
    base = Image.new("RGB", (CARD_W, CARD_H), COLOR_BG)
    layer, mask = _vertical_glow(0.45, COLOR_GLOW, 0.3)
    base = Image.composite(layer, base, mask)
    return base


def _text(draw: ImageDraw.ImageDraw, pos, text, font, fill, max_width=None, line_spacing=1.15):
    """Рисует текст с переносом по словам, если max_width задан."""
    x, y = pos
    if max_width is None:
        draw.text((x, y), text, font=font, fill=fill)
        bbox = draw.textbbox((x, y), text, font=font)
        return bbox[3]

    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    line_height = font.size * line_spacing
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _rounded_rect(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _footer(draw: ImageDraw.ImageDraw, cta_label: str, cta_value: str) -> None:
    qr_box = (MARGIN, CARD_H - 236, MARGIN + 128, CARD_H - 108)
    _rounded_rect(draw, qr_box, 24, fill=(33, 28, 23), outline=COLOR_BORDER, width=2)
    # грубая имитация QR — декоративная, не функциональная
    for i in range(4):
        for j in range(4):
            if (i + j) % 2 == 0:
                x0 = qr_box[0] + 20 + i * 22
                y0 = qr_box[1] + 20 + j * 22
                draw.rectangle([x0, y0, x0 + 16, y0 + 16], fill=COLOR_TEXT)

    label_font = _font("body", 26)
    value_font = _font("display", 40, "Bold")
    draw.text((CARD_W - MARGIN, CARD_H - 230), cta_label, font=label_font, fill=COLOR_FAINT, anchor="ra")
    draw.text((CARD_W - MARGIN, CARD_H - 190), cta_value, font=value_font, fill=COLOR_TEXT, anchor="ra")


def render_episode_card(
    week_number: int,
    metric_name: str,
    title: str,
    date_range: str,
    days_done: str,
    best_value: str,
    quote: str,
) -> bytes:
    img = _background()
    draw = ImageDraw.Draw(img)

    draw.text((MARGIN, 96), "СЕЗОНЫ", font=_font("display", 34, "Bold"), fill=COLOR_TEXT)
    badge_text = f"Серия {week_number}"
    badge_font = _font("display", 28, "Bold")
    bw = draw.textlength(badge_text, font=badge_font) + 64
    badge_box = (CARD_W - MARGIN - bw, 86, CARD_W - MARGIN, 86 + 64)
    _rounded_rect(draw, badge_box, 32, fill=COLOR_DONE_SOFT)
    draw.text((badge_box[0] + 32, badge_box[1] + 16), badge_text, font=badge_font, fill=COLOR_DONE)

    y = 220
    draw.text((MARGIN, y), metric_name.upper(), font=_font("body", 32, "Bold"), fill=COLOR_ACCENT_STRONG)
    y += 60
    y = _text(draw, (MARGIN, y), title, _font("display", 92, "Bold"), COLOR_TEXT, max_width=CARD_W - 2 * MARGIN)
    y += 24
    draw.text((MARGIN, y), date_range, font=_font("body", 34), fill=COLOR_MUTED)

    # Статы — друг под другом (не бок о бок): единицы метрики бывают длинными
    # ("повторения"), в один ряд с ограниченной шириной карточки они не влезут.
    y += 90
    stat_font = _font("display", 64, "Bold")
    label_font = _font("body", 26)
    content_width = CARD_W - 2 * MARGIN

    draw.text((MARGIN, y), "ДНЕЙ СДЕЛАНО", font=label_font, fill=COLOR_FAINT)
    y += 46
    y = _text(draw, (MARGIN, y), days_done, stat_font, COLOR_TEXT, max_width=content_width)

    y += 50
    draw.text((MARGIN, y), "ЛУЧШИЙ РЕЗУЛЬТАТ", font=label_font, fill=COLOR_FAINT)
    y += 46
    y = _text(draw, (MARGIN, y), best_value, stat_font, COLOR_TEXT, max_width=content_width)

    y += 70
    draw.rectangle([MARGIN, y, MARGIN + 6, y + 160], fill=COLOR_ACCENT)
    _text(draw, (MARGIN + 40, y), f"«{quote}»", _font("body", 38), COLOR_TEXT, max_width=CARD_W - 2 * MARGIN - 40)

    _footer(draw, "sezony.app", "Начни в ПН")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_reveal_card(
    season_title: str,
    tier_label: str,
    before_label: str,
    after_label: str,
    before_value: str,
    after_value: str,
    quote: str,
    next_season_label: str,
) -> bytes:
    img = _background()
    draw = ImageDraw.Draw(img)

    draw.text((MARGIN, 96), "СЕЗОНЫ", font=_font("display", 34, "Bold"), fill=COLOR_TEXT)
    badge_font = _font("display", 28, "Bold")
    badge_text = "REVEAL"
    bw = draw.textlength(badge_text, font=badge_font) + 64
    badge_box = (CARD_W - MARGIN - bw, 86, CARD_W - MARGIN, 86 + 64)
    _rounded_rect(draw, badge_box, 32, fill=COLOR_DONE_SOFT)
    draw.text((badge_box[0] + 32, badge_box[1] + 16), badge_text, font=badge_font, fill=COLOR_DONE)

    tier_font = _font("display", 26, "Bold")
    tw = draw.textlength(tier_label, font=tier_font) + 64
    tier_box = ((CARD_W - tw) / 2, 230, (CARD_W + tw) / 2, 230 + 64)
    _rounded_rect(draw, tier_box, 32, fill=COLOR_DONE_SOFT)
    draw.text((CARD_W / 2, 230 + 32), tier_label, font=tier_font, fill=COLOR_DONE, anchor="mm")

    title_font = _font("display", 76, "Bold")
    draw.text((CARD_W / 2, 400), season_title, font=title_font, fill=COLOR_TEXT, anchor="ma")

    y = 620
    value_font = _font("display", 84, "Bold")
    tag_font = _font("body", 26)
    draw.text((CARD_W / 2 - 260, y), before_value, font=value_font, fill=COLOR_TEXT, anchor="ma")
    draw.text((CARD_W / 2 - 260, y + 120), before_label.upper(), font=tag_font, fill=COLOR_FAINT, anchor="ma")
    draw.text((CARD_W / 2 + 260, y), after_value, font=value_font, fill=COLOR_ACCENT_STRONG, anchor="ma")
    draw.text((CARD_W / 2 + 260, y + 120), after_label.upper(), font=tag_font, fill=COLOR_FAINT, anchor="ma")

    y += 260
    quote_box = (MARGIN, y, CARD_W - MARGIN, y + 180)
    _rounded_rect(draw, quote_box, 28, outline=COLOR_BORDER, width=2, fill=COLOR_SURFACE_RAISED)
    _text(draw, (MARGIN + 36, y + 36), f"«{quote}»", _font("body", 36), COLOR_TEXT, max_width=CARD_W - 2 * MARGIN - 72)

    _footer(draw, "sezony.app · следующий сезон", next_season_label)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def save_card(data: bytes, directory: str, filename: str) -> str:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    full_path = path / filename
    full_path.write_bytes(data)
    return str(full_path).replace("\\", "/")
