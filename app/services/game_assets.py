"""
Картинки игровых сущностей (v6a): герой/личности/питомцы/боссы/рамки/фоны/
бейджи. Пока везде заглушки — SVG с силуэтом и подписью в стиле приложения.

Структура на диске (чтобы потом просто положить PNG с тем же именем):
    app/static/game/hero/hero_1..5.png
    app/static/game/persona/{warrior,sage,monk,healer,bard}_1..5.png
    app/static/game/pets/{fox,owl,drake}_1..5.png
    app/static/game/bosses/{laziness,procrastination,sleepiness,sugar,scroll,doubt}.png
    app/static/game/frames/frame_<rarity>_<n>.png
    app/static/game/bg/bg_<n>.png
    app/static/game/badges/<achievement>.png

`game_asset_url()` возвращает ссылку на реальный файл (через уже
существующий маунт /static), если он есть на диске, и на роут-заглушку
/game-placeholder/... если файла ещё нет — шаблонам эта разница не видна.
"""

import os

STATIC_GAME_DIR = os.path.join("app", "static", "game")


def game_asset_url(category: str, filename: str) -> str:
    """
    category: hero / persona / pets / bosses / frames / bg / badges
    filename: например "hero_3.png", "warrior_2.png", "laziness.png"
    """
    disk_path = os.path.join(STATIC_GAME_DIR, category, filename)
    if os.path.isfile(disk_path):
        return f"/static/game/{category}/{filename}"
    name_without_ext = os.path.splitext(filename)[0]
    return f"/game-placeholder/{category}/{name_without_ext}"


def hero_image_url(stage: int) -> str:
    return game_asset_url("hero", f"hero_{stage}.png")


def persona_image_url(persona_code: str, stage: int) -> str:
    return game_asset_url("persona", f"{persona_code}_{stage}.png")


def pet_image_url(pet_code: str, stage: int) -> str:
    return game_asset_url("pets", f"{pet_code}_{stage}.png")


def boss_image_url(boss_code: str) -> str:
    return game_asset_url("bosses", f"{boss_code}.png")


def frame_image_url(rarity: str, variant: int) -> str:
    return game_asset_url("frames", f"frame_{rarity}_{variant}.png")


def bg_image_url(variant: int) -> str:
    return game_asset_url("bg", f"bg_{variant}.png")


def badge_image_url(achievement_code: str) -> str:
    return game_asset_url("badges", f"{achievement_code}.png")
