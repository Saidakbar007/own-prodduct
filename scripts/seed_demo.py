"""
Демо-данные (§15 Фаза 2 / деплой; обновлено UX-правкой — пролога больше
нет, сезон стартует сразу): пользователь demo на 12-м дне сезона «5 км»
(с пропуском, спасённым вторым шансом, и двумя замерами) + один
завершённый сезон с Reveal. Запускать только на пустой базе:

    python scripts/seed_demo.py

Безопасно вызывать повторно — если пользователь demo уже есть, скрипт
ничего не делает и выходит.
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from sqlmodel import Session, select  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.database import engine  # noqa: E402
from app.migrations_runner import run_migrations  # noqa: E402
from app.models import Measurement, Season, SeasonDay, User  # noqa: E402
from app.seasons import engine as season_engine  # noqa: E402
from app.services.reveals import get_or_create_reveal  # noqa: E402
from app.services.seasons import build_all_days, create_season, today_day_number  # noqa: E402

DEMO_LOGIN = "demo"
DEMO_PASSWORD = "DemoSezony2026"
TARGET_DAY = 12  # сезон стартует сразу (без прологa) — день считается точно


def main() -> None:
    run_migrations()
    with Session(engine) as db:
        existing = db.exec(select(User).where(User.login == DEMO_LOGIN)).first()
        if existing:
            print(f"Пользователь '{DEMO_LOGIN}' уже существует — ничего не делаю.")
            return

        demo = User(
            login=DEMO_LOGIN,
            email="demo@sezony.app",
            password_hash=hash_password(DEMO_PASSWORD),
            name="Демо Демченко",
            birth_year=1995,
            timezone="Asia/Tashkent",
        )
        db.add(demo)
        db.commit()
        db.refresh(demo)

        # --- Сезон 1: run_5k, сегодня — ровно день 12, в процессе ---
        today = date.today()
        active_start = today - timedelta(days=TARGET_DAY - 1)
        season = create_season(
            db, uid=demo.id, template_id="run_5k", length_days=60,
            baseline_value=5, reference_date=active_start,
        )
        build_all_days(db, season)

        current_day_number = today_day_number(season, today)
        days = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season.id).order_by(SeasonDay.day_number)
        ).all()
        past_actionable = [d for d in days if d.day_number < current_day_number and d.kind != "rest"]
        rescue_day_number = past_actionable[1].day_number if len(past_actionable) > 1 else None

        for day in days:
            if day.day_number >= current_day_number or day.kind == "rest":
                continue  # "сегодня" и будущее — оставляем live, дни отдыха не трогаем
            if day.day_number == rescue_day_number:
                day.status = "rescued"
            else:
                day.status = "done"
            day.done_at = datetime.now(timezone.utc)
            db.add(day)

        season.second_chances_left = max(
            0, season_engine.second_chances_for_length(60) - (1 if rescue_day_number else 0)
        )
        db.add(season)
        db.add(Measurement(season_id=season.id, day_number=1, value=5.0))  # точка старта (день 1)
        db.add(Measurement(season_id=season.id, day_number=7, value=8.0))
        db.commit()
        db.refresh(season)

        # --- Сезон 2: pushups_50, завершён, с Reveal ---
        past_start = today - timedelta(days=45)
        season2 = create_season(
            db, uid=demo.id, template_id="pushups_50", length_days=30,
            baseline_value=5, reference_date=past_start,
        )
        build_all_days(db, season2)

        days2 = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season2.id).order_by(SeasonDay.day_number)
        ).all()
        for day in days2:
            if day.status == "rest":
                continue
            day.status = "done"
            day.done_at = datetime.now(timezone.utc)
            db.add(day)
        season2.status = "finished"
        db.add(season2)
        db.add(Measurement(season_id=season2.id, day_number=30, value=38.0))
        db.commit()
        db.refresh(season2)

        get_or_create_reveal(db, season2)

        print(
            f"Готово: demo (id={demo.id}), сезон 1 (id={season.id}, день "
            f"{current_day_number}/60), сезон 2 (id={season2.id}, finished+Reveal)."
        )


if __name__ == "__main__":
    main()
