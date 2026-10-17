"""
Профиль героя: 5 сфер (Сила/Интеллект/Дисциплина/Здоровье/Харизма),
уровень каждой 1-20. XP в сферу логируется отдельно от общих очков
(через PointsLog.sphere) с дневным лимитом на сферу — античит против
прокачки одной сферы кучей привычек за один день.
"""

from datetime import date, datetime, timezone

from sqlmodel import Session, select

from app.models import PointsLog

SPHERES = {
    "strength": "Сила",
    "intellect": "Интеллект",
    "discipline": "Дисциплина",
    "health": "Здоровье",
    "charisma": "Харизма",
}

XP_PER_LEVEL = 50  # линейная кривая: 50 XP = +1 уровень
MAX_LEVEL = 20
DAILY_SPHERE_CAP = 100  # максимум XP в одну сферу за календарный день


def sphere_level(xp: int) -> int:
    """Уровень сферы (1-20) по накопленному в ней XP."""
    return min(MAX_LEVEL, 1 + xp // XP_PER_LEVEL)


def sphere_xp(db: Session, uid: int, sphere: str) -> int:
    """Суммарный XP пользователя в конкретной сфере."""
    logs = db.exec(select(PointsLog).where(PointsLog.uid == uid, PointsLog.sphere == sphere)).all()
    return sum(log.points for log in logs)


def all_spheres_progress(db: Session, uid: int) -> list[dict]:
    """Прогресс по всем 5 сферам — для радара и профиля."""
    result = []
    for code, name in SPHERES.items():
        xp = sphere_xp(db, uid, code)
        result.append({"code": code, "name": name, "xp": xp, "level": sphere_level(xp)})
    return result


def _xp_logged_today_for_sphere(db: Session, uid: int, sphere: str) -> int:
    today = date.today()
    logs = db.exec(select(PointsLog).where(PointsLog.uid == uid, PointsLog.sphere == sphere)).all()
    return sum(log.points for log in logs if log.time.date() == today)


def log_sphere_xp(db: Session, uid: int, sphere: str, points: int) -> int:
    """
    Пишет XP в сферу с учётом дневного лимита (100/день/сфера).
    Возвращает реально начисленный XP (может быть меньше points, если лимит почти исчерпан).
    """
    if points <= 0:
        return 0

    already_today = _xp_logged_today_for_sphere(db, uid, sphere)
    remaining = max(0, DAILY_SPHERE_CAP - already_today)
    awarded = min(points, remaining)

    if awarded > 0:
        db.add(PointsLog(uid=uid, points=awarded, sphere=sphere, time=datetime.now(timezone.utc)))
        db.commit()

    return awarded
