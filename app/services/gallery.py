"""
Витрина всех игровых ассетов (v6d, /admin/gallery): по каждой стадии/
предмету — подпись, редкость/цена (у предметов), пометка "заглушка",
если на диске ещё нет реального файла. Счётчик готовности учитывает
только то, что реально должно быть картинкой — титулы и эффекты отметки
всегда текстовые (без картинки с v6a), не входят в счёт (см. DECISIONS.md, п.17).
"""

import os

from sqlmodel import Session, select

from app.models import Achievement, ShopItem
from app.services.achievements import CATALOG as ACHIEVEMENTS_CATALOG
from app.services.bosses import BOSSES
from app.services.game_assets import (
    STATIC_GAME_DIR,
    badge_image_url,
    bg_image_url,
    boss_image_url,
    frame_image_url,
    hero_image_url,
    persona_image_url,
    pet_image_url,
)
from app.services.levels import RANKS
from app.services.personas import PERSONA_IMAGE_CODE, PERSONAS, STAGE_BRACKETS
from app.services.pets import PET_SPECIES, STAGE_STREAK_THRESHOLDS
from app.services.shop import RARITY_LABELS

IMAGE_LESS_SLOTS = {"title", "effect"}  # текстовые с v6a — не входят в счёт готовности


def _has_real_file(category: str, base_name: str) -> bool:
    for ext in (".webp", ".png"):
        if os.path.isfile(os.path.join(STATIC_GAME_DIR, category, base_name + ext)):
            return True
    return False


def _hero_entries() -> list[dict]:
    entries = []
    for stage in range(1, 6):
        entries.append(
            {
                "label": f"Герой · стадия {stage}/5",
                "sublabel": f"ранг {_rank_name(stage)}",
                "image_url": hero_image_url(stage),
                "has_art": _has_real_file("hero", f"hero_{stage}"),
            }
        )
    return entries


def _rank_name(stage: int) -> str:
    return RANKS[stage - 1][2]


def _persona_entries() -> list[dict]:
    entries = []
    for sphere_code, persona_name in PERSONAS.items():
        image_code = PERSONA_IMAGE_CODE[sphere_code]
        for low, high, stage in STAGE_BRACKETS:
            entries.append(
                {
                    "label": f"{persona_name} · стадия {stage} · ур. сферы {low}–{high}",
                    "sublabel": persona_name,
                    "image_url": persona_image_url(image_code, stage),
                    "has_art": _has_real_file("persona", f"{image_code}_{stage}"),
                }
            )
    return entries


def _pet_entries() -> list[dict]:
    entries = []
    for code, name in PET_SPECIES.items():
        for stage, threshold in enumerate(STAGE_STREAK_THRESHOLDS, start=1):
            entries.append(
                {
                    "label": f"{name} · {threshold} дней серии" if threshold else f"{name} · старт (0 дней)",
                    "sublabel": name,
                    "image_url": pet_image_url(code, stage),
                    "has_art": _has_real_file("pets", f"{code}_{stage}"),
                }
            )
    return entries


def _boss_entries() -> list[dict]:
    entries = []
    for code, name in BOSSES.items():
        entries.append(
            {
                "label": name,
                "sublabel": "босс недели",
                "image_url": boss_image_url(code),
                "has_art": _has_real_file("bosses", code),
            }
        )
    return entries


def _shop_item_entry(item: ShopItem) -> dict:
    price_label = "Не продаётся" if item.price is None else f"{item.price} монет"
    source = "магазин"
    if item.season_code:
        source = "сезонный трек"
        price_label = "только через трек"
    elif item.price is None:
        source = "легендарный, не выдаётся"

    image_url = None
    has_art = True  # по умолчанию "готово" для слотов без картинки (титул/эффект)
    if item.slot == "bg" and item.image_name:
        variant = item.image_name.split("_")[-1]
        image_url = bg_image_url(variant)
        has_art = _has_real_file("bg", item.image_name)
    elif item.slot == "frame" and item.image_name:
        parts = item.image_name.split("_")
        rarity, variant = parts[-2], parts[-1]
        image_url = frame_image_url(rarity, variant)
        has_art = _has_real_file("frames", item.image_name)

    return {
        "label": item.name,
        "sublabel": f"{RARITY_LABELS.get(item.rarity, item.rarity)} · {price_label} · выдаётся: {source}",
        "image_url": image_url,
        "has_art": has_art,
        "needs_art": item.slot not in IMAGE_LESS_SLOTS,
    }


def _shop_slot_entries(db: Session, slot: str) -> list[dict]:
    items = db.exec(select(ShopItem).where(ShopItem.slot == slot)).all()
    items.sort(key=lambda i: (i.price is None, i.price or 0))
    return [_shop_item_entry(i) for i in items]


def _season_item_entries(db: Session) -> list[dict]:
    items = db.exec(select(ShopItem).where(ShopItem.season_code.is_not(None))).all()
    return [_shop_item_entry(i) for i in items]


def _badge_entries(db: Session) -> list[dict]:
    entries = []
    achievements = db.exec(select(Achievement)).all()
    by_code = {a.code: a for a in achievements}
    for code, name, description, icon, category, tier in ACHIEVEMENTS_CATALOG:
        achievement = by_code.get(code)
        tier_label = {"bronze": "бронза", "silver": "серебро", "gold": "золото"}.get(tier, "—")
        entries.append(
            {
                "label": name,
                "sublabel": f"{tier_label} · {description}",
                "image_url": badge_image_url(code),
                "has_art": _has_real_file("badges", code),
                "icon": icon,
            }
        )
    return entries


def build_gallery(db: Session) -> dict:
    """Все вкладки галереи + общий счётчик готовности арта."""
    tabs = [
        {"code": "hero", "label": "Герой", "entries": _hero_entries()},
        {"code": "personas", "label": "Личности", "entries": _persona_entries()},
        {"code": "pets", "label": "Питомцы", "entries": _pet_entries()},
        {"code": "bosses", "label": "Боссы", "entries": _boss_entries()},
        {"code": "bg", "label": "Фоны", "entries": _shop_slot_entries(db, "bg")},
        {"code": "frames", "label": "Рамки", "entries": _shop_slot_entries(db, "frame")},
        {"code": "titles", "label": "Титулы", "entries": _shop_slot_entries(db, "title")},
        {"code": "effects", "label": "Эффекты отметки", "entries": _shop_slot_entries(db, "effect")},
        {"code": "badges", "label": "Значки достижений", "entries": _badge_entries(db)},
        {"code": "season", "label": "Сезонные предметы", "entries": _season_item_entries(db)},
    ]

    # Вкладка "Сезонные предметы" дублирует записи из "Фоны"/"Рамки" для
    # удобства просмотра — не считаем их дважды в счётчике готовности.
    done = 0
    total = 0
    for tab in tabs:
        if tab["code"] == "season":
            continue
        for entry in tab["entries"]:
            if entry.get("needs_art", True):
                total += 1
                if entry["has_art"]:
                    done += 1

    return {"tabs": tabs, "done": done, "total": total}
