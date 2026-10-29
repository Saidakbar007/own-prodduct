"""
Trust score (0-100, §9): штрафы за подозрительные паттерны — повторно
используемое фото (perceptual hash), пустой/смазанный снимок, неправдоподобный
скачок в замере. При trust < 40 человек не попадает в общие составы волны (§9).
"""

MIN_TRUST_FOR_SQUAD = 40

PENALTY_DUPLICATE_PHOTO = 15
PENALTY_BLURRY_OR_BLANK_PHOTO = 5
PENALTY_IMPLAUSIBLE_MEASUREMENT = 20

DEFAULT_MAX_RELATIVE_JUMP = 0.25  # 25% от предыдущего замера за одну неделю


def apply_trust_penalty(current_score: int, penalty: int) -> int:
    return max(0, min(100, current_score - penalty))


def apply_trust_bonus(current_score: int, bonus: int) -> int:
    return max(0, min(100, current_score + bonus))


def is_measurement_plausible(
    previous_value: float | None,
    new_value: float,
    max_relative_jump: float = DEFAULT_MAX_RELATIVE_JUMP,
) -> bool:
    """Неправдоподобный скачок замера — изменение больше max_relative_jump от
    предыдущего значения за один шаг (замеры раз в неделю). Первый замер
    сезона (нет предыдущего) всегда правдоподобен."""
    if previous_value is None or previous_value == 0:
        return True
    relative_change = abs(new_value - previous_value) / abs(previous_value)
    return relative_change <= max_relative_jump


def meets_squad_trust_threshold(trust_score: int) -> bool:
    """§9: при trust < 40 человек не попадает в общие составы волны."""
    return trust_score >= MIN_TRUST_FOR_SQUAD
