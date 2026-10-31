"""
Чистые функции ядра "Сезонов" (§6 ТЗ): выбор и адаптация фазы, волны и
пролог, сборка дней сезона, второй шанс, итоговый статус, прогноз
результата, безопасность. Ничего не знает о базе данных, HTTP или времени
на часах — принимает простые значения, возвращает простые значения, поэтому
полностью покрывается юнит-тестами таблицами случаев (tests/test_engine.py).

Примечание по безопасности набора/снижения веса (§6): жёсткий недельный
лимit (``clamp_weight_target``) осмысленен только для метрики "вес тела".
Из пяти стартовых шаблонов это только fat_loss_safe (direction=down) — в
muscle_gain выбрана метрика "рабочий вес в приседе" (не вес тела), чтобы
``target_default`` имел единый смысл "изменение от baseline" для всех
шаблонов разом (см. SEASONS_SPEC.md → «Изменения»); поэтому clamp_weight_target
для muscle_gain намеренно не вызывается — прогрессия силы не ограничена
лимитом роста массы тела.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal, Optional, Sequence

from app.seasons.schema import Phase, SeasonTemplate

DayStatus = Literal["planned", "done", "minimal", "missed", "rescued", "rest"]
ResultTier = Literal["clean", "passed", "completed"]

SECOND_CHANCES_PER_30_DAYS = 3
RESCUE_WINDOW_DAYS = 1  # "до конца следующего дня"
PHASE_ADAPT_THRESHOLD = 0.15  # ±15%
SAFE_WEEKLY_LOSS_RATE = 0.01  # ≤1% массы тела в неделю
SAFE_WEEKLY_GAIN_RATE = 0.005  # ≤0.5% массы тела в неделю
MIN_BMI = 18.5


# --------------------------------------------------------------------- фазы

def select_starting_phase(template: SeasonTemplate, baseline_value: float) -> Phase:
    """Стартовая фаза по тесту уровня: самая продвинутая фаза, чей порог
    пройден. При равных порогах (несколько фаз с одинаковым
    unlock_if_baseline_gte, как в fat_loss_safe/muscle_gain, где фазы идут
    по времени, а не по уровню) выбирается самая ранняя — иначе сезон у
    всех начинался бы сразу с последней фазы."""
    phases = sorted(template.phases, key=lambda p: p.phase)
    selected = phases[0]
    best_threshold = selected.unlock_if_baseline_gte
    for phase in phases[1:]:
        if phase.unlock_if_baseline_gte <= baseline_value and phase.unlock_if_baseline_gte > best_threshold:
            selected = phase
            best_threshold = phase.unlock_if_baseline_gte
    return selected


def adapt_phase(
    template: SeasonTemplate,
    current_phase_number: int,
    measured_value: float,
    expected_value: float,
    max_phase_jump: int = 1,
) -> int:
    """Предложенный номер фазы по результату замера (§6): без изменений в
    пределах ±15% от ожидаемого, иначе на один шаг вперёд/назад, не дальше
    границ библиотеки фаз шаблона и не больше max_phase_jump за раз."""
    if expected_value == 0:
        return current_phase_number

    phase_numbers = sorted(p.phase for p in template.phases)
    ratio = measured_value / expected_value

    if ratio >= 1 + PHASE_ADAPT_THRESHOLD:
        step = 1
    elif ratio <= 1 - PHASE_ADAPT_THRESHOLD:
        step = -1
    else:
        return current_phase_number

    step = max(-max_phase_jump, min(max_phase_jump, step))
    target = current_phase_number + step
    return max(phase_numbers[0], min(phase_numbers[-1], target))


def schedule_respects_safety(template: SeasonTemplate) -> bool:
    """Проверка, что в шаблоне действительно минимум
    safety.rest_days_min_per_week дней отдыха в неделе (7 минус тренировочные)."""
    rest_days_per_week = 7 - len(set(template.schedule.train_days))
    return rest_days_per_week >= template.safety.rest_days_min_per_week


# --------------------------------------------------------------------- волна

def week_bucket_start(reference_date: date) -> date:
    """Понедельник недели, в которую попадает reference_date.

    Сезон больше не ждёт понедельника (UX-правка): день 1 — всегда
    reference_date. Это значение используется только как метка недели, по
    которой человека группируют в команду с теми, кто начал сезон на той же
    неделе — волна осталась фоном, а не точкой старта."""
    return reference_date - timedelta(days=reference_date.weekday())


# ------------------------------------------------------------- второй шанс

def second_chances_for_length(length_days: int) -> int:
    """3 вторых шанса на каждые 30 дней сезона."""
    return (length_days // 30) * SECOND_CHANCES_PER_30_DAYS


def can_rescue_day(day_date: date, today: date) -> bool:
    """Пропущенный день можно спасти до конца следующего дня включительно."""
    return day_date <= today <= day_date + timedelta(days=RESCUE_WINDOW_DAYS)


# --------------------------------------------------------------- дни сезона

@dataclass(frozen=True)
class PlannedDay:
    day_number: int
    calendar_date: date
    kind: Literal["train", "rest", "measure"]
    title: str
    instructions: str
    minimal_version: str


DAY1_TITLE = "Точка старта"
DAY1_INSTRUCTIONS = (
    "Зафиксируй, с чего начинаешь, и, если хочешь, сними фото «до» — "
    "пригодится для сравнения в финале."
)


def build_season_days(
    template: SeasonTemplate,
    phase: Phase,
    start_date: date,
    length_days: int,
    weekdays: Sequence[int],
    until_day_number: Optional[int] = None,
) -> list[PlannedDay]:
    """Строит дни сезона с day_number=1 по start_date.

    Тренировочные дни — по weekdays (1=пн..7=вс, из них циклически берутся
    шаблоны дня из текущей фазы). Дни замера — каждые measure_every_days
    (считая от начала сезона) и обязательно последний день сезона (финал).
    Остальное — восстановление. Параметр until_day_number позволяет строить
    сезон не целиком, а скользящим окном вперёд (§6) — остальное достраивается
    повторным вызовом позже с тем же start_date.
    """
    limit = min(length_days, until_day_number or length_days)
    weekday_set = set(weekdays)
    day_templates = phase.days

    result: list[PlannedDay] = []
    train_index = 0

    for offset in range(limit):
        day_number = offset + 1
        calendar_date = start_date + timedelta(days=offset)
        iso_weekday = calendar_date.isoweekday()  # 1..7, пн..вс

        if day_number == 1:
            # Пролога нет (UX-правка): день 1 сам — точка старта вместо
            # невидимого "дня 0", замер+фото "до" происходят здесь.
            result.append(
                PlannedDay(
                    day_number=1,
                    calendar_date=calendar_date,
                    kind="measure",
                    title=DAY1_TITLE,
                    instructions=DAY1_INSTRUCTIONS,
                    minimal_version="",
                )
            )
            continue

        is_measure_day = (
            day_number % template.measure_every_days == 0 or day_number == length_days
        )

        if is_measure_day:
            result.append(
                PlannedDay(
                    day_number=day_number,
                    calendar_date=calendar_date,
                    kind="measure",
                    title=template.measure.prompt,
                    instructions=template.measure.prompt,
                    minimal_version="",
                )
            )
        elif iso_weekday in weekday_set:
            day_tpl = day_templates[train_index % len(day_templates)]
            train_index += 1
            result.append(
                PlannedDay(
                    day_number=day_number,
                    calendar_date=calendar_date,
                    kind="train",
                    title=day_tpl.title,
                    instructions=day_tpl.instructions,
                    minimal_version=day_tpl.minimal,
                )
            )
        else:
            result.append(
                PlannedDay(
                    day_number=day_number,
                    calendar_date=calendar_date,
                    kind="rest",
                    title=template.rest_day.title,
                    instructions=template.rest_day.instructions,
                    minimal_version=template.rest_day.instructions,
                )
            )

    return result


# ------------------------------------------------------------ итоговый статус

def result_tier(statuses: Sequence[DayStatus]) -> ResultTier:
    """«Чистый сезон» (§6): ≥95% дней done/rescued и без missed подряд.
    «Сезон пройден»: ≥75% (minimal считается за половину). Иначе — «завершён»."""
    counted = [s for s in statuses if s != "rest"]
    if not counted:
        return "completed"

    done_strict = sum(1 for s in counted if s in ("done", "rescued"))
    minimal_count = sum(1 for s in counted if s == "minimal")
    strict_share = done_strict / len(counted)
    weighted_share = (done_strict + 0.5 * minimal_count) / len(counted)

    has_consecutive_missed = any(
        a == "missed" and b == "missed" for a, b in zip(counted, counted[1:])
    )

    if strict_share >= 0.95 and not has_consecutive_missed:
        return "clean"
    if weighted_share >= 0.75:
        return "passed"
    return "completed"


def adherence_14d(statuses_last_14_days: Sequence[DayStatus]) -> float:
    """(done + rescued + 0.5·minimal) / запланированные дни за последние 14
    дней (дни отдыха в расчёт не входят — они не "план")."""
    counted = [s for s in statuses_last_14_days if s != "rest"]
    if not counted:
        return 1.0
    done = sum(1 for s in counted if s in ("done", "rescued"))
    minimal = sum(1 for s in counted if s == "minimal")
    return (done + 0.5 * minimal) / len(counted)


# ----------------------------------------------------------------- прогноз

def forecast_by_plan(
    current_value: float,
    remaining_sessions: int,
    expected_progress_per_session: float,
    adherence: float,
) -> float:
    """Прогноз по плану: текущее значение + оставшиеся тренировки ×
    ожидаемый прогресс за тренировку × adherence_14d."""
    return current_value + remaining_sessions * expected_progress_per_session * adherence


def forecast_by_measurements(
    values: Sequence[float], remaining_weeks: float
) -> Optional[float]:
    """Линейный тренд по последним ≤4 замерам, продлённый на remaining_weeks
    недель вперёд. None, если замеров меньше двух — тренд не построить."""
    recent = list(values)[-4:]
    if len(recent) < 2:
        return None

    n = len(recent)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(recent) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    slope = 0.0 if denom == 0 else sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, recent)) / denom
    return recent[-1] + slope * remaining_weeks


def forecast_result(
    current_value: float,
    remaining_sessions: int,
    expected_progress_per_session: float,
    adherence: float,
    measurement_values: Sequence[float],
    remaining_weeks: float,
) -> float:
    """Итоговый прогноз к финалу (§6): меньше 2 замеров — чисто по плану;
    иначе 40% план / 60% тренд по замерам."""
    plan_value = forecast_by_plan(
        current_value, remaining_sessions, expected_progress_per_session, adherence
    )
    measured_value = forecast_by_measurements(measurement_values, remaining_weeks)
    if measured_value is None:
        return plan_value
    return 0.4 * plan_value + 0.6 * measured_value


# ---------------------------------------------------------------- безопасность

def safe_weekly_change_limit(direction: Literal["up", "down"]) -> float:
    """Доля массы тела в неделю: ≤1% при снижении, ≤0.5% при наборе (§6)."""
    return SAFE_WEEKLY_LOSS_RATE if direction == "down" else SAFE_WEEKLY_GAIN_RATE


def clamp_weight_target(
    baseline_value: float,
    raw_target_value: float,
    direction: Literal["up", "down"],
    weeks: float,
) -> float:
    """Ограничивает цель по весу тела безопасным темпом. Если цель требует
    больше — возвращает цель по безопасному темпу вместо исходной (§6)."""
    if weeks <= 0 or baseline_value <= 0:
        return raw_target_value

    max_change = baseline_value * safe_weekly_change_limit(direction) * weeks
    if direction == "down":
        safe_floor = baseline_value - max_change
        return max(raw_target_value, safe_floor)
    safe_ceiling = baseline_value + max_change
    return min(raw_target_value, safe_ceiling)


def bmi(weight_kg: float, height_cm: float) -> float:
    if height_cm <= 0:
        raise ValueError("height_cm должен быть больше 0")
    height_m = height_cm / 100
    return weight_kg / (height_m**2)


def meets_fat_loss_eligibility(weight_kg: float, height_cm: float) -> bool:
    """§5: при ИМТ < 18.5 шаблон fat_loss_safe недоступен."""
    return bmi(weight_kg, height_cm) >= MIN_BMI
