"""
Округление по существу (§8 docs/specs/NEWLIFE_V8_SPEC.md) — каждое число, которое видит
пользователь, идёт через этот модуль. Чистые функции, шаг может
переопределяться шаблоном цели (см. app/newlife/goal_catalog.py).

| Величина       | Шаг по умолчанию |
|----------------|-------------------|
| вес на штанге  | 2.5 кг            |
| гантели        | 1 кг до 10, 2 кг выше |
| повторения     | целые             |
| вес тела       | 0.1 кг            |
| обхваты        | 0.5 см            |
| время бега     | 30 сек            |
| шаги           | 500               |
| сон            | 15 мин            |
| деньги         | 1000 сум          |
| проценты       | целые             |
"""

from __future__ import annotations

import math

BARBELL_STEP_KG = 2.5
DUMBBELL_STEP_LOW_KG = 1.0  # до 10 кг
DUMBBELL_STEP_HIGH_KG = 2.0  # выше 10 кг
DUMBBELL_THRESHOLD_KG = 10.0
BODYWEIGHT_STEP_KG = 0.1
CIRCUMFERENCE_STEP_CM = 0.5
RUN_TIME_STEP_SEC = 30
STEPS_STEP = 500
SLEEP_STEP_MIN = 15
MONEY_STEP_SUM = 1000
FORECAST_DAYS_WEEKS_THRESHOLD = 21


def round_to_step(value: float, step: float) -> float:
    """Округление к ближайшему кратному step (обычное математическое)."""
    if step <= 0:
        return value
    return round(value / step) * step


def round_barbell(kg: float, step: float = BARBELL_STEP_KG) -> float:
    return round_to_step(kg, step)


def round_dumbbell(kg: float) -> float:
    step = DUMBBELL_STEP_LOW_KG if kg <= DUMBBELL_THRESHOLD_KG else DUMBBELL_STEP_HIGH_KG
    return round_to_step(kg, step)


def round_reps(n: float) -> int:
    return round(n)


def round_bodyweight(kg: float) -> float:
    return round(round_to_step(kg, BODYWEIGHT_STEP_KG), 1)


def round_circumference(cm: float) -> float:
    return round(round_to_step(cm, CIRCUMFERENCE_STEP_CM), 1)


def round_run_time_seconds(seconds: float) -> int:
    return int(round_to_step(seconds, RUN_TIME_STEP_SEC))


def round_steps(n: float) -> int:
    return int(round_to_step(n, STEPS_STEP))


def round_sleep_minutes(minutes: float) -> int:
    return int(round_to_step(minutes, SLEEP_STEP_MIN))


def round_money(amount: float, step: float = MONEY_STEP_SUM) -> int:
    return int(round_to_step(amount, step))


def round_percent(p: float) -> int:
    return round(p)


def forecast_unit_and_value(days: float) -> tuple[str, int]:
    """Прогноз срока (§8): ≤21 дня — в днях, иначе в неделях ("примерно N нед.").
    Возвращает (unit, n), где unit — "days" | "weeks"; текст собирает шаблон/i18n."""
    d = round(days)
    if d <= FORECAST_DAYS_WEEKS_THRESHOLD:
        return ("days", max(0, d))
    weeks = round(days / 7)
    return ("weeks", max(1, weeks))


def rolling_average(values: list[float], window: int = 7) -> float | None:
    """Скользящее среднее за последние window значений (§7: вес тела, шаги,
    сон усредняются за 7 дней, чтобы шум не пугал человека)."""
    if not values:
        return None
    recent = values[-window:]
    return sum(recent) / len(recent)
