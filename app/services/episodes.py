"""
«Серия» (§7.5) — итог недели. Название генерируется по событиям недели
(шаблонные фразы), не ИИ. Карточка — PNG через app/services/cards.py.
"""

import json
from datetime import date, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.models import Episode, Measurement, Season, SeasonDay
from app.services.cards import render_episode_card

TITLE_TEMPLATES = {
    "clean_week": "Неделя без единого пропуска",
    "comeback": "Несмотря ни на что — досмотрели до конца",
    "best_measure": "Новый личный лучший результат",
    "steady": "Ровная, рабочая неделя",
    "first_week": "Первые шаги позади",
}


def week_bounds(season: Season, week_number: int) -> tuple[date, date]:
    start = season.start_date + timedelta(days=(week_number - 1) * 7)
    end = min(season.end_date, start + timedelta(days=6))
    return start, end


def _pick_title(week_days: list[SeasonDay], week_number: int, measurements: list[Measurement]) -> str:
    statuses = [d.status for d in week_days if d.kind != "measure"]
    if week_number == 1:
        return TITLE_TEMPLATES["first_week"]
    if statuses and all(s in ("done",) for s in statuses):
        return TITLE_TEMPLATES["clean_week"]
    if "missed" in statuses and any(s in ("done", "minimal", "rescued") for s in statuses):
        return TITLE_TEMPLATES["comeback"]
    if len(measurements) >= 2 and measurements[-1].value >= max(m.value for m in measurements[:-1]):
        return TITLE_TEMPLATES["best_measure"]
    return TITLE_TEMPLATES["steady"]


def get_or_create_episode(db: Session, season: Season, week_number: int) -> Optional[Episode]:
    existing = db.exec(
        select(Episode).where(Episode.season_id == season.id, Episode.week_number == week_number)
    ).first()
    if existing:
        return existing

    start, end = week_bounds(season, week_number)
    if end > date.today():
        return None  # неделя ещё не закончилась — рано генерировать

    week_days = db.exec(
        select(SeasonDay).where(
            SeasonDay.season_id == season.id,
            SeasonDay.calendar_date >= start,
            SeasonDay.calendar_date <= end,
        )
    ).all()
    if not week_days:
        return None

    measurements = db.exec(
        select(Measurement).where(Measurement.season_id == season.id).order_by(Measurement.day_number)
    ).all()

    done_count = sum(1 for d in week_days if d.status in ("done", "minimal", "rescued"))
    total_count = sum(1 for d in week_days if d.kind != "measure")
    title = _pick_title(week_days, week_number, measurements)

    summary = {
        "days_done": f"{done_count}/{total_count}" if total_count else "0/0",
        "date_range": f"{start.strftime('%d.%m')}–{end.strftime('%d.%m')}",
        "best_value": measurements[-1].value if measurements else season.baseline_value,
    }

    episode = Episode(
        season_id=season.id,
        week_number=week_number,
        title=title,
        summary_json=json.dumps(summary, ensure_ascii=False),
    )
    db.add(episode)
    db.commit()
    db.refresh(episode)
    return episode


def episode_card_png(season: Season, episode: Episode) -> bytes:
    summary = json.loads(episode.summary_json)
    return render_episode_card(
        week_number=episode.week_number,
        metric_name=season.title,
        title=episode.title,
        date_range=summary["date_range"],
        days_done=summary["days_done"],
        best_value=f"{summary['best_value']} {season.metric_unit}",
        quote=episode.title,
    )
