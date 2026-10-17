"""
5 личностей героя — по одной на каждую сферу (v6a). Личность не хранится
отдельной таблицей: всё считается "на лету" из `PointsLog` (который уже
пишет XP по сферам, см. app/services/spheres.py) — так состояние личности
никогда не расходится с реальной активностью пользователя.
"""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import PointsLog
from app.services.spheres import SPHERES, sphere_level, sphere_xp

PERSONAS = {
    "strength": "Воин",
    "intellect": "Мудрец",
    "discipline": "Монах",
    "health": "Целитель",
    "charisma": "Бард",
}

# Латинские коды для имён файлов картинок (warrior_1.png и т.д.) — отдельно
# от кодов сфер, потому что в задании имена файлов заданы по-английски.
PERSONA_IMAGE_CODE = {
    "strength": "warrior",
    "intellect": "sage",
    "discipline": "monk",
    "health": "healer",
    "charisma": "bard",
}

# Стадия личности 1-5 по уровню сферы (1-20)
STAGE_BRACKETS = [(1, 3, 1), (4, 7, 2), (8, 11, 3), (12, 15, 4), (16, 20, 5)]

LEADING_WINDOW_DAYS = 14
HARMONY_WINDOW_DAYS = 7

ACTIVE_MAX_DAYS = 3
SLEEPING_MIN_DAYS = 21

WAKING_XP_BONUS = 0.5  # +50% XP за первую отметку после "спит"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def persona_stage(level: int) -> int:
    """Стадия личности (1-5) по уровню сферы (см. DECISIONS.md, раздел 2)."""
    for low, high, stage in STAGE_BRACKETS:
        if low <= level <= high:
            return stage
    return STAGE_BRACKETS[-1][2]


def days_since_last_activity(db: Session, uid: int, sphere: str) -> int | None:
    """Сколько дней прошло с последней XP-записи в этой сфере. None — активности не было никогда."""
    last_log = db.exec(
        select(PointsLog)
        .where(PointsLog.uid == uid, PointsLog.sphere == sphere)
        .order_by(PointsLog.time.desc())
    ).first()
    if not last_log:
        return None

    last_time = last_log.time
    if last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=timezone.utc)
    return (_now() - last_time).days


def persona_state(days_since: int | None) -> str:
    """Состояние личности: активна / дремлет / спит (никогда не активировалась = спит)."""
    if days_since is None or days_since >= SLEEPING_MIN_DAYS:
        return "спит"
    if days_since <= ACTIVE_MAX_DAYS:
        return "активна"
    return "дремлет"


def is_waking(db: Session, uid: int, sphere: str) -> bool:
    """
    True, если личность реально "спала" (была активна когда-то, затем 21+ дней
    тишины) — следующая отметка будет "пробуждением". У личности, которая
    никогда не активировалась, нет "сна", из которого просыпаться — это старт,
    не пробуждение, поэтому бонус здесь не даём (иначе он бы срабатывал
    на самой первой отметке вообще у всех, что не соответствует задумке).
    """
    days_since = days_since_last_activity(db, uid, sphere)
    if days_since is None:
        return False
    return days_since >= SLEEPING_MIN_DAYS


def _sphere_xp_since(db: Session, uid: int, sphere: str, since: datetime) -> int:
    logs = db.exec(select(PointsLog).where(PointsLog.uid == uid, PointsLog.sphere == sphere)).all()
    return sum(log.points for log in logs if log.time >= since)


def leading_persona_sphere(db: Session, uid: int) -> str:
    """Сфера с наибольшим XP за последние 14 дней — её личность "ведущая"."""
    since = _now() - timedelta(days=LEADING_WINDOW_DAYS)
    best_sphere = next(iter(SPHERES))
    best_xp = -1
    for code in SPHERES:  # порядок SPHERES — тай-брейк при равенстве
        xp = _sphere_xp_since(db, uid, code, since)
        if xp > best_xp:
            best_xp = xp
            best_sphere = code
    return best_sphere


def has_harmony(db: Session, uid: int) -> bool:
    """Все 5 личностей были активны (хоть одна отметка) за последние 7 дней."""
    since_days = HARMONY_WINDOW_DAYS
    for code in SPHERES:
        days = days_since_last_activity(db, uid, code)
        if days is None or days > since_days:
            return False
    return True


def persona_profile(db: Session, uid: int) -> list[dict]:
    """Полный профиль всех 5 личностей — для страницы /hero."""
    leading = leading_persona_sphere(db, uid)
    profile = []
    for code, sphere_name in SPHERES.items():
        xp = sphere_xp(db, uid, code)
        level = sphere_level(xp)
        days_since = days_since_last_activity(db, uid, code)
        profile.append(
            {
                "sphere_code": code,
                "sphere_name": sphere_name,
                "persona_name": PERSONAS[code],
                "level": level,
                "stage": persona_stage(level),
                "state": persona_state(days_since),
                "days_since_activity": days_since,
                "is_leading": code == leading,
            }
        )
    return profile
