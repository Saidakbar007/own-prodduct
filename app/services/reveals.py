"""
Reveal (§7.8) — финал сезона: статус, «было -> стало», PNG-карточка для
сторис. Видео (§10) — Фаза 3.
"""

from typing import Optional

from sqlmodel import Session, select

from app.models import Measurement, Reveal, Season, SeasonDay
from app.seasons import engine
from app.services.cards import render_reveal_card

TIER_LABELS = {
    "clean": "ЧИСТЫЙ СЕЗОН",
    "passed": "СЕЗОН ПРОЙДЕН",
    "completed": "СЕЗОН ЗАВЕРШЁН",
}


def get_or_create_reveal(db: Session, season: Season) -> Reveal:
    existing = db.exec(select(Reveal).where(Reveal.season_id == season.id)).first()
    if existing:
        return existing

    statuses = db.exec(
        select(SeasonDay.status).where(SeasonDay.season_id == season.id).order_by(SeasonDay.day_number)
    ).all()
    tier = engine.result_tier(statuses)

    measurements = db.exec(
        select(Measurement.value).where(Measurement.season_id == season.id).order_by(Measurement.day_number)
    ).all()
    after_value = measurements[-1] if measurements else season.baseline_value

    reveal = Reveal(
        season_id=season.id,
        tier=tier,
        before_value=season.baseline_value,
        after_value=after_value,
    )
    db.add(reveal)

    season.result_tier = tier
    db.add(season)
    db.commit()
    db.refresh(reveal)
    return reveal


def reveal_card_png(season: Season, reveal: Reveal, next_season_label: str) -> bytes:
    # Единица метрики — в подпись, а не в большую цифру: бывает длинной
    # ("повторения"), с цифрой в один ряд на 1080px она не влезает.
    unit = season.metric_unit
    return render_reveal_card(
        season_title=season.title,
        tier_label=TIER_LABELS.get(reveal.tier, reveal.tier.upper()),
        before_label=f"{unit} · день 0",
        after_label=f"{unit} · день {season.length_days}",
        before_value=str(reveal.before_value),
        after_value=str(reveal.after_value),
        quote="Ты сделал то, на что решаются единицы.",
        next_season_label=next_season_label,
    )
