"""
Картинки игровых сущностей: герой/личности уже настоящий арт (v6c, WebP,
нарезан из 3D-рендеров скриптом scripts/process_art.py — см. его docstring
и DECISIONS.md, раздел 14). Питомцы/боссы/рамки/фоны/бейджи — пока
заглушки: SVG с силуэтом и подписью в стиле приложения.

Структура на диске (чтобы положить готовый файл — просто кладём файл с
тем же именем, искать будет сначала .webp, потом .png):
    app/static/game/hero/hero_1..5.webp
    app/static/game/persona/{warrior,sage,monk,healer,bard}_1..5.webp
    app/static/game/pets/{fox,owl,drake}_1..5.png
    app/static/game/bosses/{laziness,procrastination,sleepiness,sugar,scroll,doubt}.png
    app/static/game/frames/frame_<rarity>_<n>.png
    app/static/game/bg/bg_<n>.png
    app/static/game/badges/<achievement>.png

`game_asset_url()` возвращает ссылку на реальный файл (через уже
существующий маунт /static) в порядке .webp -> .png, если он есть на
диске, и на роут-заглушку /game-placeholder/... если файла ещё нет —
шаблонам эта разница не видна.
"""

import os

STATIC_GAME_DIR = os.path.join("app", "static", "game")

# Порядок предпочтения расширений при поиске готового файла на диске.
ASSET_EXTENSIONS = (".webp", ".png")


def game_asset_url(category: str, base_name: str) -> str:
    """
    category: hero / persona / pets / bosses / frames / bg / badges
    base_name: имя файла БЕЗ расширения, например "hero_3", "warrior_2", "laziness"
    """
    for ext in ASSET_EXTENSIONS:
        disk_path = os.path.join(STATIC_GAME_DIR, category, base_name + ext)
        if os.path.isfile(disk_path):
            return f"/static/game/{category}/{base_name}{ext}"
    return f"/game-placeholder/{category}/{base_name}"


def hero_image_url(stage: int) -> str:
    return game_asset_url("hero", f"hero_{stage}")


def persona_image_url(persona_code: str, stage: int) -> str:
    return game_asset_url("persona", f"{persona_code}_{stage}")


def pet_image_url(pet_code: str, stage: int) -> str:
    return game_asset_url("pets", f"{pet_code}_{stage}")


def boss_image_url(boss_code: str) -> str:
    return game_asset_url("bosses", boss_code)


def frame_image_url(rarity: str, variant: int) -> str:
    return game_asset_url("frames", f"frame_{rarity}_{variant}")


def bg_image_url(variant: int) -> str:
    return game_asset_url("bg", f"bg_{variant}")


def badge_image_url(achievement_code: str) -> str:
    return game_asset_url("badges", achievement_code)
