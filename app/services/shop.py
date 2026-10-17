"""
Магазин и инвентарь (v6a). За монеты — только косметика и заморозка серии,
никогда XP/уровни/место в рейтинге (см. DECISIONS.md, п.4-5).

Слоты: bg (фон профиля) / frame (рамка аватара) / title (титул) /
effect (эффект отметки) — экипируются по одному на слот; freeze
(заморозка серии) — расходуемый товар, не экипируется, хранится до
FREEZE_MAX_STOCK штук.
"""

from datetime import date, datetime, time, timezone

from sqlmodel import Session, select

from app.models import Habit, HabitHistory, InventoryItem, ShopItem, User

FREEZE_MAX_STOCK = 2
FREEZE_PRICE = 40

RARITY_ORDER = ["common", "rare", "epic", "legendary"]
RARITY_LABELS = {"common": "Обычный", "rare": "Редкий", "epic": "Эпический", "legendary": "Легендарный"}

EPIC_MIN_HERO_LEVEL = 20

# code, slot, rarity, name, price (None = не продаётся), image_name
CATALOG = [
    # --- Фоны профиля (12): 5 обычных, 4 редких, 2 эпических, 1 легендарный ---
    ("bg_dawn", "bg", "common", "Рассвет", 50, "bg_1"),
    ("bg_fog", "bg", "common", "Туман", 55, "bg_2"),
    ("bg_steppe", "bg", "common", "Степь", 60, "bg_3"),
    ("bg_pebble", "bg", "common", "Галька", 65, "bg_4"),
    ("bg_dust", "bg", "common", "Пыль дорог", 70, "bg_5"),
    ("bg_midnight", "bg", "rare", "Полночь", 150, "bg_6"),
    ("bg_storm", "bg", "rare", "Шторм", 180, "bg_7"),
    ("bg_aurora", "bg", "rare", "Северное сияние", 200, "bg_8"),
    ("bg_desert", "bg", "rare", "Пустыня", 220, "bg_9"),
    ("bg_volcano", "bg", "epic", "Вулкан", 400, "bg_10"),
    ("bg_starpath", "bg", "epic", "Звёздный путь", 500, "bg_11"),
    ("bg_legend", "bg", "legendary", "Корона легенды", None, "bg_12"),
    # --- Рамки аватара (12): 5/4/2/1 ---
    ("frame_simple", "frame", "common", "Простая рамка", 50, "frame_common_1"),
    ("frame_wood", "frame", "common", "Деревянная рамка", 55, "frame_common_2"),
    ("frame_stone", "frame", "common", "Каменная рамка", 60, "frame_common_3"),
    ("frame_braid", "frame", "common", "Плетёная рамка", 65, "frame_common_4"),
    ("frame_forged", "frame", "common", "Кованая рамка", 70, "frame_common_5"),
    ("frame_silver", "frame", "rare", "Серебряная рамка", 150, "frame_rare_1"),
    ("frame_rune", "frame", "rare", "Рунная рамка", 180, "frame_rare_2"),
    ("frame_ice", "frame", "rare", "Ледяная рамка", 200, "frame_rare_3"),
    ("frame_flame", "frame", "rare", "Огненная рамка", 220, "frame_rare_4"),
    ("frame_gold", "frame", "epic", "Золотая рамка", 400, "frame_epic_1"),
    ("frame_dragon", "frame", "epic", "Драконья рамка", 500, "frame_epic_2"),
    ("frame_legend", "frame", "legendary", "Рамка легенды", None, "frame_legendary_1"),
    # --- Титулы (10): 4/3/2/1 ---
    ("title_starter", "title", "common", "Новичок пути", 50, None),
    ("title_persistent", "title", "common", "Упорный", 60, None),
    ("title_early_bird", "title", "common", "Ранняя пташка", 70, None),
    ("title_steady", "title", "common", "Стойкий", 80, None),
    ("title_streak_keeper", "title", "rare", "Хранитель серии", 150, None),
    ("title_routine_master", "title", "rare", "Мастер режима", 180, None),
    ("title_inspirer", "title", "rare", "Вдохновитель", 220, None),
    ("title_unshakeable", "title", "epic", "Непоколебимый", 400, None),
    ("title_discipline_legend", "title", "epic", "Легенда дисциплины", 600, None),
    ("title_five_voices", "title", "legendary", "Голос пяти личностей", None, None),
    # --- Эффекты отметки (5): 2/2/1/0 ---
    ("effect_sparks", "effect", "common", "Искры", 50, None),
    ("effect_glow", "effect", "common", "Лёгкое сияние", 70, None),
    ("effect_wave", "effect", "rare", "Волна энергии", 150, None),
    ("effect_flame_trail", "effect", "rare", "Огненный след", 220, None),
    ("effect_supernova", "effect", "epic", "Взрыв суперновой", 500, None),
    # --- Заморозка серии (расходуемая, не экипируется) ---
    ("freeze", "freeze", "common", "Заморозка серии", FREEZE_PRICE, None),
]


def ensure_shop_seeded(db: Session) -> None:
    """Заполняет каталог магазина, если он пуст (безопасно перезапускать)."""
    for code, slot, rarity, name, price, image_name in CATALOG:
        existing = db.exec(select(ShopItem).where(ShopItem.code == code)).first()
        if existing:
            continue
        min_level = EPIC_MIN_HERO_LEVEL if rarity == "epic" else 1
        db.add(
            ShopItem(
                code=code, slot=slot, rarity=rarity, name=name,
                price=price, min_hero_level=min_level, image_name=image_name,
            )
        )
    db.commit()


def owned_codes(db: Session, uid: int) -> set[str]:
    rows = db.exec(select(InventoryItem).where(InventoryItem.uid == uid)).all()
    return {r.item_code for r in rows}


def is_owned(db: Session, uid: int, code: str) -> bool:
    return code in owned_codes(db, uid)


def buy_item(db: Session, user: User, code: str, hero_level: int) -> tuple[bool, str]:
    """Покупка товара за монеты. Возвращает (успех, сообщение для пользователя)."""
    item = db.exec(select(ShopItem).where(ShopItem.code == code)).first()
    if not item:
        return False, "Товар не найден"
    if item.price is None:
        return False, "Этот предмет не продаётся"
    if hero_level < item.min_hero_level:
        return False, f"Нужен уровень героя не ниже {item.min_hero_level}"

    if item.slot == "freeze":
        if user.freeze_stock >= FREEZE_MAX_STOCK:
            return False, f"Заморозок уже максимум ({FREEZE_MAX_STOCK}) — нельзя хранить больше"
        if user.coins < item.price:
            return False, "Не хватает монет"
        user.coins -= item.price
        user.freeze_stock += 1
        db.add(user)
        db.commit()
        return True, f"+1 заморозка (в запасе {user.freeze_stock}/{FREEZE_MAX_STOCK})"

    if is_owned(db, user.id, code):
        return False, "Этот предмет уже куплен"
    if user.coins < item.price:
        return False, "Не хватает монет"

    user.coins -= item.price
    db.add(user)
    db.add(InventoryItem(uid=user.id, item_code=code))
    db.commit()
    return True, f"Куплено: {item.name}"


def equip_item(db: Session, user: User, code: str) -> tuple[bool, str]:
    """Надевает предмет в его слот (bg/frame/title/effect) — должен быть уже куплен."""
    item = db.exec(select(ShopItem).where(ShopItem.code == code)).first()
    if not item:
        return False, "Товар не найден"
    if item.slot == "freeze":
        return False, "Заморозку нельзя надеть — она расходуется"
    if not is_owned(db, user.id, code):
        return False, "Сначала нужно купить этот предмет"

    setattr(user, f"equipped_{item.slot}", code)
    db.add(user)
    db.commit()
    return True, f"Надето: {item.name}"


def use_freeze(db: Session, user: User, habit: Habit, day: date) -> tuple[bool, str]:
    """
    Тратит 1 запасённую заморозку на конкретный ПРОПУЩЕННЫЙ день (без
    единой отметки) — превращает его в "skip" задним числом, что не
    прерывает серию (см. DECISIONS.md, п.5). День не может быть в будущем
    или сегодняшним (на сегодня используется обычная отметка).
    """
    if user.freeze_stock <= 0:
        return False, "Нет запасённых заморозок"

    from app.services.usertime import today_for

    today = today_for(user)
    if day >= today:
        return False, "Заморозку можно применить только к прошедшему дню"

    day_start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    day_end = datetime.combine(day, time.max, tzinfo=timezone.utc)
    existing = db.exec(
        select(HabitHistory).where(
            HabitHistory.h_id == habit.id, HabitHistory.time >= day_start, HabitHistory.time <= day_end
        )
    ).first()
    if existing:
        return False, "На этот день уже есть отметка"

    user.freeze_stock -= 1
    db.add(user)
    db.add(HabitHistory(h_id=habit.id, time=day_start, kind="skip"))
    db.commit()
    return True, f"Заморозка применена — «{habit.name}» за {day.isoformat()} не прервёт серию"
