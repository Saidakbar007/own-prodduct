"""
Логика очков и уровней.
"""

from sqlmodel import Session, select

from app.models import Level, PointsLog, User

# Пороги очков для названий уровней (от меньшего к большему)
LEVEL_THRESHOLDS = [
    (0, "Новичок"),
    (100, "Ученик"),
    (300, "Практик"),
    (700, "Мастер"),
    (1500, "Легенда"),
]

# Очки по сложности (сервер сам решает, сколько дать — клиент не присылает очки)
HABIT_DIFFICULTY_POINTS = {"easy": 5, "medium": 10, "hard": 20}
GOAL_DIFFICULTY_POINTS = {"easy": 50, "medium": 100, "hard": 200}
DIFFICULTY_LABELS = {"easy": "Легко", "medium": "Средне", "hard": "Сложно"}


def points_for_habit_difficulty(difficulty: str) -> int:
    """Очки за отметку привычки по выбранной сложности (по умолчанию «Средне»)."""
    return HABIT_DIFFICULTY_POINTS.get(difficulty, HABIT_DIFFICULTY_POINTS["medium"])


def points_for_goal_difficulty(difficulty: str) -> int:
    """Очки за выполнение цели по выбранной сложности (по умолчанию «Средне»)."""
    return GOAL_DIFFICULTY_POINTS.get(difficulty, GOAL_DIFFICULTY_POINTS["medium"])


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


def award_points(db: Session, user: User, points: int) -> tuple[Level, bool]:
    """
    Добавляет очки пользователю, пересчитывает название уровня, пишет в журнал
    очков (для недельного рейтинга). Возвращает (уровень, повысился ли уровень).
    """
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    if not level:
        level = Level(uid=user.id, point=0, name="Новичок")

    old_name = level.name
    level.point += points
    level.name = level_name_for_points(level.point)

    db.add(level)
    db.add(PointsLog(uid=user.id, points=points))
    db.commit()
    db.refresh(level)
    return level, level.name != old_name
