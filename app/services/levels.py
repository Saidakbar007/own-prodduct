"""
Уровни героя (1-50) и 5 рангов. XP до следующего уровня L -> L+1 растёт:
80 + 20*L. Хранится только суммарный накопленный XP (Level.point, то же
поле что и раньше) — номер уровня и ранг всегда считаются из него, так что
никакой отдельной миграции данных не нужно: старые очки сразу попадают в
новую шкалу (см. DECISIONS.md, раздел 1).
"""

MAX_LEVEL = 50

# (нижняя граница уровня, верхняя граница уровня, название ранга)
RANKS = [
    (1, 5, "Новичок"),
    (6, 15, "Ученик"),
    (16, 25, "Практик"),
    (26, 40, "Мастер"),
    (41, 50, "Легенда"),
]


def xp_for_level(level: int) -> int:
    """XP, нужный чтобы пройти С уровня level НА level+1."""
    return 80 + 20 * level


def _build_thresholds() -> list[int]:
    """thresholds[i] = суммарный XP, нужный чтобы ДОСТИЧЬ уровня i+1 (с нуля)."""
    thresholds = [0]
    total = 0
    for level in range(1, MAX_LEVEL):
        total += xp_for_level(level)
        thresholds.append(total)
    return thresholds


_THRESHOLDS = _build_thresholds()


def level_for_xp(total_xp: int) -> int:
    """Номер уровня (1-50) по суммарному накопленному XP."""
    total_xp = max(0, total_xp)
    level = 1
    for i, threshold in enumerate(_THRESHOLDS):
        if total_xp >= threshold:
            level = i + 1
    return min(level, MAX_LEVEL)


def rank_for_level(level: int) -> str:
    """Название ранга (Новичок/Ученик/Практик/Мастер/Легенда) по номеру уровня."""
    for low, high, name in RANKS:
        if low <= level <= high:
            return name
    return RANKS[-1][2]


def rank_index_for_level(level: int) -> int:
    """Номер ранга (1-5) — он же используется как "стадия героя"."""
    for i, (low, high, _name) in enumerate(RANKS, start=1):
        if low <= level <= high:
            return i
    return len(RANKS)


def level_up_message(level_number: int) -> str:
    """
    Текст тоста при повышении номера уровня. Если этот уровень — первый в
    своём ранге, упоминает и новый ранг (иначе просто номер уровня).
    """
    rank = rank_for_level(level_number)
    is_rank_start = any(low == level_number for low, _high, _name in RANKS)
    if is_rank_start:
        return f"⭐ Новый уровень: {level_number}! Открыт ранг «{rank}»"
    return f"⭐ Новый уровень: {level_number}!"


def level_progress(total_xp: int) -> dict:
    """
    Полный прогресс по суммарному XP: номер уровня, ранг, стадия героя (1-5),
    сколько XP набрано внутри текущего уровня, сколько нужно для следующего,
    и процент заполнения полоски до следующего уровня.
    """
    level = level_for_xp(total_xp)
    rank = rank_for_level(level)
    stage = rank_index_for_level(level)

    if level >= MAX_LEVEL:
        return {
            "level": level,
            "rank": rank,
            "stage": stage,
            "xp_into_level": 0,
            "xp_for_next_level": None,
            "percent": 100,
            "next_rank": None,
        }

    current_threshold = _THRESHOLDS[level - 1]
    xp_into_level = total_xp - current_threshold
    xp_needed = xp_for_level(level)
    percent = int((xp_into_level / xp_needed) * 100) if xp_needed else 100

    next_rank = rank_for_level(level + 1)
    if next_rank == rank:
        next_rank = None  # следующий уровень не меняет ранг — не показываем его отдельно

    return {
        "level": level,
        "rank": rank,
        "stage": stage,
        "xp_into_level": max(0, xp_into_level),
        "xp_for_next_level": xp_needed,
        "percent": max(0, min(100, percent)),
        "next_rank": next_rank,
    }
