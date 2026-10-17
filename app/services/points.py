"""
Логика очков и уровней.
"""

from sqlmodel import Session, select

from app.models import Level, PointsLog, User
from app.services.levels import level_for_xp, rank_for_level

# Старые пороги очков — оставлены только для обратной совместимости тестов,
# которые проверяли прежнюю (до v6a) систему названий уровней по сумме очков.
# Текущая система — ранги по НОМЕРУ УРОВНЯ (см. app/services/levels.py).
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
    """Название РАНГА (Новичок/Ученик/.../Легенда) по сумме очков — через новую шкалу уровней (v6a)."""
    return rank_for_level(level_for_xp(points))


def next_level_info(points: int) -> tuple[str, int] | None:
    """
    Устаревшая (до v6a) функция — оставлена только для обратной совместимости
    импортов. Новый код должен использовать `app.services.levels.level_progress`.
    Возвращает (название следующего ранга, сколько очков до него не хватает),
    либо None, если уже максимальный ранг.
    """
    from app.services.levels import level_progress

    progress = level_progress(points)
    if not progress["next_rank"]:
        return None
    return progress["next_rank"], progress["xp_for_next_level"] - progress["xp_into_level"]


def award_points(db: Session, user: User, points: int, apply_trust: bool = True) -> tuple[Level, bool]:
    """
    Добавляет очки пользователю, пересчитывает ранг, пишет в журнал очков
    (для недельного рейтинга). Очки масштабируются множителем trust score
    (0.5x-1.0x), если apply_trust=True. Возвращает (уровень, повысился ли
    НОМЕР уровня 1-50 — не только название ранга, которое меняется гораздо реже).
    """
    if apply_trust:
        from app.services.trust import trust_multiplier

        points = round(points * trust_multiplier(user.trust_score))

    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    if not level:
        level = Level(uid=user.id, point=0, name="Новичок")

    old_level_number = level_for_xp(level.point)
    level.point += points
    level.name = level_name_for_points(level.point)
    new_level_number = level_for_xp(level.point)

    db.add(level)
    db.add(PointsLog(uid=user.id, points=points))
    db.commit()
    db.refresh(level)
    return level, new_level_number != old_level_number
