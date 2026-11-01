"""
Демо-данные (§15 Фаза 2 / деплой; обновлено UX-правкой — пролога больше
нет, сезон стартует сразу; обновлено NewLife v8 §16 — добавлена точка А,
цель "Набрать массу" на 3-й неделе, 3 привычки, 1 плохая привычка с
трендом вниз, обязательные дела учёба+работа, 2 чек-ина): пользователь
demo на 12-м дне сезона «5 км» (с пропуском, спасённым вторым шансом, и
двумя замерами) + один завершённый сезон с Reveal + полный профиль v8.
Запускать только на пустой базе:

    python scripts/seed_demo.py

Безопасно вызывать повторно — если пользователь demo уже есть, скрипт
ничего не делает и выходит.
"""

import json
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
from app.models import (  # noqa: E402
    BadHabit,
    Commitment,
    Habit,
    Measurement,
    Profile,
    Season,
    SeasonDay,
    SphereState,
    User,
)
from app.seasons import engine as season_engine  # noqa: E402
from app.services.checkin_service import log_checkin  # noqa: E402
from app.services.habits import log_bad_habit_slip, log_habit  # noqa: E402
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

        # --- NewLife v8: точка А, цель "Набрать массу" на 3-й неделе ---
        profile = Profile(
            uid=demo.id,
            height_cm=178,
            weight_kg=68.0,
            wake_time="07:00",
            sleep_time="23:00",
            chronotype="morning",
            daily_minutes=30,
            constraints_json=json.dumps(["has_pullup_bar"]),
            main_obstacle="tired",
            onboarding_done_at=datetime.now(timezone.utc),
        )
        db.add(profile)
        for sphere_id in (
            "body", "mind", "character", "social", "career", "finance",
            "relationships", "knowledge", "values", "lifestyle", "energy",
        ):
            db.add(SphereState(
                uid=demo.id, sphere_id=sphere_id,
                level=6 if sphere_id == "body" else 4,
                priority=1 if sphere_id == "body" else 2,
                active=sphere_id == "body",
            ))
        db.commit()

        mass_start = today - timedelta(days=16)  # сегодня — 17-й день, 3-я неделя
        season3 = create_season(
            db, uid=demo.id, template_id="muscle_gain", length_days=90,
            baseline_value=68.0, secondary_baseline_value=60.0,
            reference_date=mass_start, sphere_id="body",
        )
        build_all_days(db, season3)
        day_num3 = today_day_number(season3, today)
        days3 = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season3.id).order_by(SeasonDay.day_number)
        ).all()
        for day in days3:
            if day.day_number >= day_num3 or day.kind == "rest":
                continue
            day.status = "done"
            day.done_at = datetime.now(timezone.utc)
            db.add(day)
        db.add(Measurement(season_id=season3.id, day_number=1, value=68.0))
        db.commit()

        commitments = [
            Commitment(
                uid=demo.id, title="Учёба", category="study",
                weekdays_json=json.dumps([1, 2, 3, 4, 5]),
                start_time="09:00", end_time="13:00",
            ),
            Commitment(
                uid=demo.id, title="Работа", category="work",
                weekdays_json=json.dumps([1, 2, 3, 4, 5]),
                start_time="14:00", end_time="18:00",
            ),
        ]
        db.add_all(commitments)
        db.commit()

        habits = [
            Habit(
                uid=demo.id, catalog_id="water_morning", title="Стакан воды с утра",
                spheres_json=json.dumps(["body", "energy"]), days_json=json.dumps([1, 2, 3, 4, 5, 6, 7]),
                time_pref="morning", duration_min=2, minimal_version="Сделать хотя бы глоток",
            ),
            Habit(
                uid=demo.id, catalog_id="stretch_morning", title="Утренняя растяжка",
                spheres_json=json.dumps(["body"]), days_json=json.dumps([1, 2, 3, 4, 5, 6, 7]),
                time_pref="morning", duration_min=10, minimal_version="2 минуты растяжки",
            ),
            Habit(
                uid=demo.id, catalog_id="walk_daily", title="Дневная прогулка",
                spheres_json=json.dumps(["body", "energy"]), days_json=json.dumps([1, 2, 3, 4, 5, 6, 7]),
                time_pref="day", duration_min=20, minimal_version="5 минут на свежем воздухе",
            ),
        ]
        db.add_all(habits)
        db.commit()
        for h in habits:
            db.refresh(h)
        for offset in range(7, 0, -1):
            log_date = today - timedelta(days=offset)
            for h in habits:
                status = "missed" if offset == 4 else "done"
                log_habit(db, habit_id=h.id, on_date=log_date, status=status, now=datetime.now(timezone.utc))

        bad_habit = BadHabit(
            uid=demo.id, catalog_id="social_media_scroll", title="Бесцельный скролл соцсетей",
            triggers_json=json.dumps(["boredom", "stress", "automatic", "procrastination"]),
            replacement_id="read_book", baseline_per_day=90.0, target_per_day=30.0, unit="minutes",
        )
        db.add(bad_habit)
        db.commit()
        db.refresh(bad_habit)
        declining_minutes = [85, 75, 70, 60, 55, 45, 40]  # тренд вниз за последнюю неделю
        for offset, minutes in zip(range(7, 0, -1), declining_minutes):
            log = log_bad_habit_slip(
                db, bad_habit_id=bad_habit.id, on_date=today - timedelta(days=offset),
                trigger_id="boredom", now=datetime.now(timezone.utc),
            )
            log.value = float(minutes)
            db.add(log)
        db.commit()

        log_checkin(db, uid=demo.id, on_date=today - timedelta(days=1), energy=3, stress=3, mood=3)
        log_checkin(db, uid=demo.id, on_date=today, energy=4, stress=2, mood=4)

        print(
            f"Готово: demo (id={demo.id}), сезон 1 (id={season.id}, день "
            f"{current_day_number}/60), сезон 2 (id={season2.id}, finished+Reveal), "
            f"сезон 3 — Набрать массу (id={season3.id}, день {day_num3}/90, 3-я неделя), "
            f"профиль+11 сфер, 2 обязательных дела, 3 привычки, 1 плохая привычка "
            f"(тренд вниз), 2 чек-ина."
        )


if __name__ == "__main__":
    main()
