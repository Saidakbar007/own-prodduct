"""
Логика очков и уровней.
"""

from sqlmodel import Session, select

from app.models import Level, User

# Пороги очков для названий уровней (от меньшего к большему)
LEVEL_THRESHOLDS = [
    (0, "Новичок"),
    (100, "Ученик"),
    (300, "Практик"),
    (700, "Мастер"),
    (1500, "Легенда"),
]


def level_name_for_points(points: int) -> str:
    """Возвращает название уровня по количеству очков."""
    name = LEVEL_THRESHOLDS[0][1]
    for threshold, level_name in LEVEL_THRESHOLDS:
        if points >= threshold:
            name = level_name
    return name


def next_level_info(points: int) -> tuple[str, int] | None:
    """
    Возвращает (название следующего уровня, сколько очков до него не хватает).
    Если уровень уже максимальный — возвращает None.
    """
    for threshold, level_name in LEVEL_THRESHOLDS:
        if points < threshold:
            return level_name, threshold - points
    return None


def award_points(db: Session, user: User, points: int) -> Level:
    """Добавляет очки пользователю и пересчитывает название уровня."""
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    if not level:
        level = Level(uid=user.id, point=0, name="Новичок")

    level.point += points
    level.name = level_name_for_points(level.point)

    db.add(level)
    db.commit()
    db.refresh(level)
    return level
