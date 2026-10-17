"""
Сезон (v6b): 4 недели, тема + бесплатный трек на 30 ступеней. Прогресс —
живой запрос по сумме XP с начала сезона (без отдельного поля), награды
по ступеням — статическая лестница в коде (как CATALOG в shop.py). Каждая
5-я ступень даёт сезонный предмет, остальные — монеты (см. DECISIONS.md, п.13).
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import PointsLog, Season, SeasonClaim, ShopItem, User

SEASON_CODE = "season1"
SEASON_NAME = "Сезон пробуждения"
SEASON_THEME = "Первые шаги героя — тема возвращения к себе после долгой зимы"
SEASON_DURATION_DAYS = 28

MAX_STEPS = 30
XP_PER_STEP = 40
ITEM_STEP_INTERVAL = 5

# Сезонные предметы — по одному на каждую 5-ю ступень (6 штук), не продаются
# за монеты, выдаются только через трек. code, slot, rarity, name, image_name
SEASON_ITEMS = [
    ("season1_bg_frost", "bg", "epic", "Иней пробуждения", "bg_s1"),
    ("season1_frame_thaw", "frame", "epic", "Рамка оттепели", "frame_season_1"),
    ("season1_title_awakened", "title", "epic", "Пробуждённый", None),
    ("season1_effect_bloom", "effect", "epic", "Эффект: расцвет", None),
    ("season1_bg_dawn2", "bg", "epic", "Рассвет сезона", "bg_s2"),
    ("season1_frame_legend", "frame", "legendary", "Рамка сезона", "frame_season_legendary"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_season_seeded(db: Session) -> Season:
    """Создаёт текущий сезон и его предметы, если их ещё нет (безопасно перезапускать)."""
    season = db.exec(select(Season).where(Season.code == SEASON_CODE)).first()
    if not season:
        season = Season(
            code=SEASON_CODE,
            name=SEASON_NAME,
            theme=SEASON_THEME,
            start_date=_now(),
            end_date=_now() + timedelta(days=SEASON_DURATION_DAYS),
        )
        db.add(season)
        db.commit()
        db.refresh(season)

    for code, slot, rarity, name, image_name in SEASON_ITEMS:
        existing = db.exec(select(ShopItem).where(ShopItem.code == code)).first()
        if not existing:
            db.add(
                ShopItem(
                    code=code, slot=slot, rarity=rarity, name=name,
                    price=None, min_hero_level=1, image_name=image_name, season_code=SEASON_CODE,
                )
            )
    db.commit()
    return season


def get_active_season(db: Session) -> Season | None:
    now = _now()
    seasons = db.exec(select(Season)).all()
    for season in seasons:
        start = season.start_date if season.start_date.tzinfo else season.start_date.replace(tzinfo=timezone.utc)
        end = season.end_date if season.end_date.tzinfo else season.end_date.replace(tzinfo=timezone.utc)
        if start <= now <= end:
            return season
    return None


def season_xp_for_user(db: Session, uid: int, season: Season) -> int:
    logs = db.exec(select(PointsLog).where(PointsLog.uid == uid)).all()
    start = season.start_date if season.start_date.tzinfo else season.start_date.replace(tzinfo=timezone.utc)
    end = season.end_date if season.end_date.tzinfo else season.end_date.replace(tzinfo=timezone.utc)
    return sum(log.points for log in logs if start <= _aware(log.time) <= end)


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def season_step(xp: int) -> int:
    return min(MAX_STEPS, xp // XP_PER_STEP)


def reward_for_step(step: int) -> dict:
    """Награда за ступень: сезонный предмет каждые 5 ступеней, иначе монеты."""
    if step % ITEM_STEP_INTERVAL == 0 and step > 0:
        index = step // ITEM_STEP_INTERVAL - 1
        if 0 <= index < len(SEASON_ITEMS):
            return {"type": "item", "code": SEASON_ITEMS[index][0], "name": SEASON_ITEMS[index][3]}
    return {"type": "coins", "amount": 5 + step}  # монеты растут со ступенями


def claimed_max_step(db: Session, uid: int, season_id: int) -> int:
    claims = db.exec(
        select(SeasonClaim).where(SeasonClaim.uid == uid, SeasonClaim.season_id == season_id)
    ).all()
    return max((c.step for c in claims), default=0)


def claim_new_steps(db: Session, user: User, season: Season) -> list[dict]:
    """Выдаёт награды за все новые пересечённые ступени с прошлого раза."""
    from app.services.coins import award_coins
    from app.services.shop import InventoryItem, is_owned

    xp = season_xp_for_user(db, user.id, season)
    current_step = season_step(xp)
    last_claimed = claimed_max_step(db, user.id, season.id)

    granted = []
    for step in range(last_claimed + 1, current_step + 1):
        reward = reward_for_step(step)
        if reward["type"] == "coins":
            awarded = award_coins(db, user, reward["amount"])
            granted.append({"step": step, "text": f"+{awarded} 🪙"})
        else:
            if not is_owned(db, user.id, reward["code"]):
                db.add(InventoryItem(uid=user.id, item_code=reward["code"]))
            granted.append({"step": step, "text": f"Сезонный предмет: {reward['name']}"})
        db.add(SeasonClaim(uid=user.id, season_id=season.id, step=step))
        db.commit()

    return granted


def season_progress(db: Session, user: User, season: Season) -> dict:
    xp = season_xp_for_user(db, user.id, season)
    step = season_step(xp)
    xp_into_step = xp - step * XP_PER_STEP
    percent = int((step / MAX_STEPS) * 100)
    return {
        "name": season.name,
        "theme": season.theme,
        "step": step,
        "max_steps": MAX_STEPS,
        "xp": xp,
        "xp_into_step": xp_into_step,
        "xp_per_step": XP_PER_STEP,
        "percent": percent,
        "end_date": season.end_date,
    }
