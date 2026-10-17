"""
Заглушки картинок для игровых сущностей (v6a) — пока нет настоящих PNG.
SVG на лету: эмодзи-силуэт + подпись, в цветах дизайн-токенов приложения.
Как только по пути из app/services/game_assets.py появится PNG — заглушка
больше не используется (см. game_asset_url()).
"""

import re

from fastapi import APIRouter, Response

router = APIRouter()

# Цвета зафиксированы (не CSS-переменные) — SVG отдаётся как отдельный файл
# без доступа к теме страницы; палитра близка к светлой теме "кодекса".
BG = "#E3E9EC"
BORDER = "#D3DCE2"
ACCENT = "#0E7C86"
TEXT = "#13202A"
MUTED = "#566874"

PERSONA_EMOJI = {"warrior": "⚔️", "sage": "📖", "monk": "🧘", "healer": "💚", "bard": "🎵"}
PET_EMOJI = {"fox": "🦊", "owl": "🦉", "drake": "🐉"}
BOSS_EMOJI = {
    "laziness": "🦥",
    "procrastination": "⏳",
    "sleepiness": "😴",
    "sugar": "🍬",
    "scroll": "📜",
    "doubt": "❓",
}
RARITY_COLORS = {
    "common": "#6B7782",
    "rare": "#13866F",
    "epic": "#9440C4",
    "legendary": "#C27407",
}
RARITY_LABELS = {"common": "обычная", "rare": "редкая", "epic": "эпическая", "legendary": "легендарная"}


def _svg(emoji: str, caption: str, accent: str = ACCENT) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
    <rect width="200" height="200" rx="16" fill="{BG}" stroke="{BORDER}" stroke-width="2"/>
    <circle cx="100" cy="82" r="48" fill="{accent}" opacity="0.12"/>
    <text x="100" y="100" font-size="56" text-anchor="middle" dominant-baseline="central">{emoji}</text>
    <text x="100" y="168" font-size="13" font-family="monospace" fill="{MUTED}" text-anchor="middle">{caption}</text>
</svg>"""


def _response(svg: str) -> Response:
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/game-placeholder/hero/{name}")
def hero_placeholder(name: str):
    stage = re.search(r"(\d+)", name)
    stage_n = stage.group(1) if stage else "?"
    return _response(_svg("🦸", f"Герой · стадия {stage_n}"))


@router.get("/game-placeholder/persona/{name}")
def persona_placeholder(name: str):
    match = re.match(r"([a-z]+)_(\d+)", name)
    code, stage_n = (match.group(1), match.group(2)) if match else (name, "?")
    emoji = PERSONA_EMOJI.get(code, "🧑")
    return _response(_svg(emoji, f"{code} · стадия {stage_n}"))


@router.get("/game-placeholder/pets/{name}")
def pet_placeholder(name: str):
    match = re.match(r"([a-z]+)_(\d+)", name)
    code, stage_n = (match.group(1), match.group(2)) if match else (name, "?")
    emoji = PET_EMOJI.get(code, "🐾")
    return _response(_svg(emoji, f"{code} · стадия {stage_n}"))


@router.get("/game-placeholder/bosses/{name}")
def boss_placeholder(name: str):
    emoji = BOSS_EMOJI.get(name, "👾")
    return _response(_svg(emoji, name, accent="#C24444"))


@router.get("/game-placeholder/frames/{name}")
def frame_placeholder(name: str):
    match = re.match(r"frame_([a-z]+)_(\d+)", name)
    rarity, variant = (match.group(1), match.group(2)) if match else ("common", "?")
    color = RARITY_COLORS.get(rarity, ACCENT)
    label = RARITY_LABELS.get(rarity, rarity)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200">
    <rect width="200" height="200" rx="16" fill="{BG}"/>
    <rect x="10" y="10" width="180" height="180" rx="12" fill="none" stroke="{color}" stroke-width="8"/>
    <rect x="26" y="26" width="148" height="148" rx="8" fill="none" stroke="{color}" stroke-width="2" opacity="0.5"/>
    <text x="100" y="188" font-size="12" font-family="monospace" fill="{MUTED}" text-anchor="middle">рамка · {label} #{variant}</text>
</svg>"""
    return _response(svg)


@router.get("/game-placeholder/bg/{name}")
def bg_placeholder(name: str):
    match = re.search(r"(\d+)", name)
    variant = match.group(1) if match else "?"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" width="400" height="200">
    <defs>
        <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="{ACCENT}" stop-opacity="0.35"/>
            <stop offset="1" stop-color="{BG}"/>
        </linearGradient>
    </defs>
    <rect width="400" height="200" fill="url(#g)"/>
    <text x="200" y="190" font-size="12" font-family="monospace" fill="{MUTED}" text-anchor="middle">фон профиля #{variant}</text>
</svg>"""
    return _response(svg)


@router.get("/game-placeholder/badges/{name}")
def badge_placeholder(name: str):
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 160" width="160" height="160">
    <circle cx="80" cy="70" r="55" fill="{ACCENT}" opacity="0.15" stroke="{ACCENT}" stroke-width="3"/>
    <text x="80" y="78" font-size="48" text-anchor="middle" dominant-baseline="central">🏆</text>
    <text x="80" y="142" font-size="11" font-family="monospace" fill="{MUTED}" text-anchor="middle">{name}</text>
</svg>"""
    return _response(svg)
