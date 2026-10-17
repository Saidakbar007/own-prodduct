"""
Магазин: каталог (фоны/рамки/титулы/эффекты + заморозка серии), покупка,
экипировка. За монеты — никогда XP/уровни/место в рейтинге.
"""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import Level, ShopItem, User
from app.rendering import render
from app.services.flash import push_flash
from app.services.levels import level_progress
from app.services.shop import CATALOG, RARITY_LABELS, RARITY_ORDER, buy_item, equip_item, owned_codes

router = APIRouter()

SLOT_LABELS = {"bg": "Фон профиля", "frame": "Рамка аватара", "title": "Титул", "effect": "Эффект отметки", "freeze": "Заморозка серии"}
SLOT_ORDER = ["bg", "frame", "title", "effect", "freeze"]


def _hero_level(db: Session, user: User) -> int:
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    return level_progress(level.point if level else 0)["level"]


def _shop_context(db: Session, user: User, error: str = None) -> dict:
    hero_level = _hero_level(db, user)
    owned = owned_codes(db, user.id)
    items = db.exec(select(ShopItem)).all()
    by_slot: dict[str, list] = {slot: [] for slot in SLOT_ORDER}
    for item in items:
        by_slot.setdefault(item.slot, []).append(
            {
                "item": item,
                "rarity_label": RARITY_LABELS.get(item.rarity, item.rarity),
                "rarity_index": RARITY_ORDER.index(item.rarity) + 1 if item.rarity in RARITY_ORDER else 1,
                "owned": item.code in owned,
                "equipped": getattr(user, f"equipped_{item.slot}", None) == item.code if item.slot != "freeze" else False,
                "can_afford": item.price is not None and user.coins >= item.price,
                "level_locked": hero_level < item.min_hero_level,
            }
        )
    for slot_items in by_slot.values():
        slot_items.sort(key=lambda d: (d["item"].price is None, d["item"].price or 0))

    return {
        "user": user,
        "error": error,
        "hero_level": hero_level,
        "slots": [{"code": slot, "label": SLOT_LABELS.get(slot, slot), "entries": by_slot.get(slot, [])} for slot in SLOT_ORDER],
    }


@router.get("/shop")
def shop_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    return render(request, "shop.html", _shop_context(db, user), db=db, user=user)


@router.post("/shop/buy/{code}")
def shop_buy(code: str, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    ok, message = buy_item(db, user, code, _hero_level(db, user))
    push_flash(request, message, "success" if ok else "error")
    return render(request, "shop.html", _shop_context(db, user), db=db, user=user, status_code=200 if ok else 400)


@router.post("/shop/equip/{code}")
def shop_equip(code: str, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    ok, message = equip_item(db, user, code)
    push_flash(request, message, "success" if ok else "error")
    return render(request, "shop.html", _shop_context(db, user), db=db, user=user, status_code=200 if ok else 400)
