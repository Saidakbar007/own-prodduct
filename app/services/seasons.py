"""
Сборка сезона в базе данных: соединяет чистые функции app/seasons/engine.py
с моделями (Wave, Season, SeasonDay, Measurement) и библиотекой шаблонов.
"""

import json
from datetime import date, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models import Measurement, Season, SeasonDay, Wave
from app.seasons import engine
from app.seasons.schema import Phase, SeasonTemplate
from app.seasons_library.loader import get_template
from app.services.squads import assign_squad

ROLLING_WINDOW_DAYS = 14
MUSCLE_GAIN_BODYWEIGHT_DEFAULT_GAIN_RATIO = 1.05  # дефолтный ориентир +5% веса тела за сезон


def get_or_create_wave(db: Session, start_date: date, template_id: Optional[str] = None) -> Wave:
    wave = db.exec(
        select(Wave).where(Wave.start_date == start_date, Wave.template_id == template_id)
    ).first()
    if wave:
        return wave
    wave = Wave(start_date=start_date, template_id=template_id)
    db.add(wave)
    db.commit()
    db.refresh(wave)
    return wave


def wave_composition_count(db: Session, wave_id: int) -> int:
    """Сколько людей уже готовятся/проходят сезон в этой волне."""
    return len(db.exec(select(Season.id).where(Season.wave_id == wave_id)).all())


def _compute_target_value(template: SeasonTemplate, baseline_value: float, length_days: int) -> float:
    direction_sign = 1 if template.metric.direction == "up" else -1
    raw_target = baseline_value + direction_sign * template.target_default
    if template.metric.direction == "down":
        weeks = length_days / 7
        return engine.clamp_weight_target(baseline_value, raw_target, "down", weeks)
    return raw_target


def create_season(
    db: Session,
    uid: int,
    template_id: str,
    length_days: int,
    baseline_value: float,
    reference_date: date,
    secondary_baseline_value: Optional[float] = None,
) -> Season:
    """Создаёт волну (если нужно), сезон и первые дни (скользящее окно),
    плюс стартовый замер (день 0 = baseline)."""
    template = get_template(template_id)
    phase = engine.select_starting_phase(template, baseline_value)
    wave_start = engine.compute_wave_start(reference_date)
    prologue_days = engine.prologue_length_days(reference_date, wave_start)
    wave = get_or_create_wave(db, wave_start, template_id)

    end_date = wave_start + timedelta(days=length_days - 1)
    target_value = _compute_target_value(template, baseline_value, length_days)

    secondary_fields: dict = {}
    if template_id == "muscle_gain" and secondary_baseline_value is not None:
        weeks = length_days / 7
        raw_secondary_target = secondary_baseline_value * MUSCLE_GAIN_BODYWEIGHT_DEFAULT_GAIN_RATIO
        secondary_target = engine.clamp_weight_target(
            secondary_baseline_value, raw_secondary_target, "up", weeks
        )
        secondary_fields = dict(
            secondary_metric_name="Вес тела",
            secondary_metric_unit="кг",
            secondary_direction="up",
            secondary_baseline_value=secondary_baseline_value,
            secondary_target_value=secondary_target,
        )

    season = Season(
        uid=uid,
        template_id=template.id,
        template_version=template.version,
        title=template.title,
        length_days=length_days,
        wave_id=wave.id,
        prologue_start=reference_date if prologue_days > 0 else None,
        start_date=wave_start,
        end_date=end_date,
        metric_name=template.metric.name,
        metric_unit=template.metric.unit,
        direction=template.metric.direction,
        baseline_value=baseline_value,
        target_value=target_value,
        projected_value=None,
        days_per_week=len(template.schedule.train_days),
        weekdays_json=json.dumps(template.schedule.train_days),
        minutes_per_day=template.schedule.minutes[1],
        status="prologue" if prologue_days > 0 else "active",
        second_chances_left=engine.second_chances_for_length(length_days),
        current_phase=phase.phase,
        **secondary_fields,
    )
    db.add(season)
    db.commit()
    db.refresh(season)

    assign_squad(db, wave.id, template.id, season.id, uid)

    build_upcoming_days(db, season, template, phase, until_date=reference_date + timedelta(days=ROLLING_WINDOW_DAYS))

    db.add(
        Measurement(
            season_id=season.id,
            day_number=0,
            value=baseline_value,
            secondary_value=secondary_baseline_value,
        )
    )
    db.commit()

    return season


def build_upcoming_days(
    db: Session, season: Season, template: SeasonTemplate, phase: Phase, until_date: date
) -> None:
    """Скользящее окно (§6): достраивает дни сезона до until_date (не дальше конца сезона)."""
    existing_max = db.exec(
        select(SeasonDay.day_number)
        .where(SeasonDay.season_id == season.id)
        .order_by(SeasonDay.day_number.desc())
    ).first()
    already_built = existing_max or 0

    until_day_number = min(season.length_days, max(0, (until_date - season.start_date).days) + 1)
    if until_day_number <= already_built:
        return

    weekdays = json.loads(season.weekdays_json)
    planned = engine.build_season_days(
        template, phase, season.start_date, season.length_days, weekdays, until_day_number=until_day_number
    )
    for day in planned:
        if day.day_number <= already_built:
            continue
        db.add(
            SeasonDay(
                season_id=season.id,
                day_number=day.day_number,
                calendar_date=day.calendar_date,
                kind=day.kind,
                title=day.title,
                instructions=day.instructions,
                minimal_version=day.minimal_version,
                status="rest" if day.kind == "rest" else "planned",
            )
        )
    db.commit()


def ensure_days_built_for_today(db: Session, season: Season, today: date) -> None:
    """Вызывается при каждом заходе на «Сегодня»/«Сезон» — достраивает окно вперёд."""
    template = get_template(season.template_id)
    phase = next(p for p in template.phases if p.phase == season.current_phase)
    build_upcoming_days(db, season, template, phase, until_date=today + timedelta(days=ROLLING_WINDOW_DAYS))


def get_active_season(db: Session, uid: int) -> Optional[Season]:
    """Текущий (ещё не завершённый) сезон пользователя, последний созданный."""
    return db.exec(
        select(Season)
        .where(Season.uid == uid, Season.status.in_(["prologue", "active"]))
        .order_by(Season.created_at.desc())
    ).first()


def get_day(db: Session, season_id: int, day_number: int) -> Optional[SeasonDay]:
    return db.exec(
        select(SeasonDay).where(SeasonDay.season_id == season_id, SeasonDay.day_number == day_number)
    ).first()


def today_day_number(season: Season, today: date) -> int:
    return (today - season.start_date).days + 1


def sync_season_state(db: Session, season: Season, today: date) -> Season:
    """Ленивая синхронизация без фонового планировщика (его пока нет — см.
    DECISIONS.md): при каждом заходе пользователя — перевод prologue->active,
    просроченные "planned" дни (кроме rest) становятся "missed", а последний
    день с терминальным статусом переводит сезон в "finished"."""
    changed = False

    if season.status == "prologue" and today >= season.start_date:
        season.status = "active"
        changed = True

    if season.status in ("prologue", "active"):
        overdue = db.exec(
            select(SeasonDay).where(
                SeasonDay.season_id == season.id,
                SeasonDay.status == "planned",
                SeasonDay.calendar_date < today,
            )
        ).all()
        for day in overdue:
            day.status = "missed"
            db.add(day)
            changed = True

        last_day = get_day(db, season.id, season.length_days)
        if last_day and last_day.status not in ("planned", "rest"):
            season.status = "finished"
            changed = True

    if changed:
        db.add(season)
        db.commit()
        db.refresh(season)

    return season


def mark_day_done(db: Session, day: SeasonDay, now, proof_id: Optional[int] = None) -> SeasonDay:
    day.status = "done"
    day.done_at = now
    day.proof_id = proof_id
    db.add(day)
    db.commit()
    db.refresh(day)
    return day


def mark_day_minimal(db: Session, day: SeasonDay, now) -> SeasonDay:
    day.status = "minimal"
    day.done_at = now
    db.add(day)
    db.commit()
    db.refresh(day)
    return day


def rescue_day(db: Session, season: Season, day: SeasonDay, now) -> SeasonDay:
    """Второй шанс (§6): день становится rescued, тратится один шанс."""
    day.status = "rescued"
    day.done_at = now
    season.second_chances_left -= 1
    db.add(day)
    db.add(season)
    db.commit()
    db.refresh(day)
    return day


def season_statuses(db: Session, season_id: int) -> list[str]:
    """Статусы всех дней сезона — для engine.result_tier/adherence_14d."""
    return db.exec(
        select(SeasonDay.status).where(SeasonDay.season_id == season_id).order_by(SeasonDay.day_number)
    ).all()
