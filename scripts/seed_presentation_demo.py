"""
Демо-аккаунт для презентации 2026-11-09 (срочный план владельца, пункт 6):
анкета заполнена, 4 активные сферы (body/mind/energy/character — первые
три полностью проработаны в 2.0: дерево сфер, паутинка, роудмап), 2
активных сезона на 3-й неделе (body: muscle_gain; mind: deep_focus),
3 полезные привычки со стриком за 14 дней, 1 вредная привычка с таймером
воздержания и трендом вниз за 14 дней, 2 обязательных дела (учёба/работа).

Логин/пароль — см. константы ниже, тоже написаны в docs/RELEASE_2.0.md
(или в финальном отчёте сессии). Отдельный логин от "demo" (не трогаем
существующий аккаунт — он принадлежит кому-то другому/остался с другой
сессии, не наш).

Безопасно вызывать повторно — если пользователь уже есть, ничего не делает.
Работает против DATABASE_URL из окружения (прод — передать явно, см. ниже).
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
    Profile,
    SeasonDay,
    SphereState,
    User,
)
from app.services.habits import log_bad_habit_slip, log_habit  # noqa: E402
from app.services.seasons import build_all_days, create_season, today_day_number  # noqa: E402

DEMO_LOGIN = "demo2026"
DEMO_PASSWORD = "Presentation2026!"


def main() -> None:
    run_migrations()
    with Session(engine) as db:
        existing = db.exec(select(User).where(User.login == DEMO_LOGIN)).first()
        if existing:
            print(f"Пользователь '{DEMO_LOGIN}' уже существует — ничего не делаю.")
            return

        today = date.today()

        user = User(
            login=DEMO_LOGIN,
            email="demo2026@newlife.app",
            password_hash=hash_password(DEMO_PASSWORD),
            name="Азиз Демо",
            birth_year=2003,
            timezone="Asia/Tashkent",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        profile = Profile(
            uid=user.id,
            height_cm=176,
            weight_kg=70.0,
            wake_time="07:00",
            sleep_time="23:30",
            chronotype="morning",
            daily_minutes=45,
            constraints_json=json.dumps(["has_pullup_bar"]),
            main_obstacle="tired",
            onboarding_done_at=datetime.now(timezone.utc),
        )
        db.add(profile)

        sphere_levels = {"body": 5, "mind": 4, "energy": 4, "character": 3}
        for sphere_id in (
            "body", "mind", "character", "social", "career", "finance",
            "relationships", "knowledge", "values", "lifestyle", "energy",
        ):
            db.add(
                SphereState(
                    uid=user.id,
                    sphere_id=sphere_id,
                    level=sphere_levels.get(sphere_id, 4),
                    priority=1 if sphere_id in sphere_levels else 2,
                    active=sphere_id in sphere_levels,
                )
            )

        commitments = [
            Commitment(
                uid=user.id, title="Учёба", category="study",
                weekdays_json=json.dumps([1, 2, 3, 4, 5]),
                start_time="09:00", end_time="13:00",
            ),
            Commitment(
                uid=user.id, title="Работа", category="work",
                weekdays_json=json.dumps([1, 2, 3, 4, 5]),
                start_time="14:30", end_time="18:30",
            ),
        ]
        db.add_all(commitments)
        db.commit()

        # --- Сезон 1: body, muscle_gain, день ~17/90 (3-я неделя) ---
        mass_start = today - timedelta(days=16)
        season_body = create_season(
            db, uid=user.id, template_id="muscle_gain", length_days=90,
            baseline_value=70.0, secondary_baseline_value=62.0,
            reference_date=mass_start, sphere_id="body",
        )
        build_all_days(db, season_body)
        day_num_body = today_day_number(season_body, today)
        days_body = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season_body.id).order_by(SeasonDay.day_number)
        ).all()
        for day in days_body:
            if day.day_number >= day_num_body or day.kind == "rest":
                continue
            day.status = "done"
            day.done_at = datetime.now(timezone.utc)
            db.add(day)
        db.commit()

        # --- Сезон 2: mind, deep_focus, день ~17/60 (3-я неделя) ---
        focus_start = today - timedelta(days=16)
        season_mind = create_season(
            db, uid=user.id, template_id="deep_focus", length_days=60,
            baseline_value=60, reference_date=focus_start, sphere_id="mind",
        )
        build_all_days(db, season_mind)
        day_num_mind = today_day_number(season_mind, today)
        days_mind = db.exec(
            select(SeasonDay).where(SeasonDay.season_id == season_mind.id).order_by(SeasonDay.day_number)
        ).all()
        for day in days_mind:
            if day.day_number >= day_num_mind or day.kind == "rest":
                continue
            day.status = "done" if day.day_number % 5 != 0 else "minimal"
            day.done_at = datetime.now(timezone.utc)
            db.add(day)
        db.commit()

        # --- Привычки (3, со стриком за 14 дней) ---
        habits = [
            Habit(
                uid=user.id, catalog_id="water_morning", title="Стакан воды с утра",
                spheres_json=json.dumps(["body", "energy"]), days_json=json.dumps([1, 2, 3, 4, 5, 6, 7]),
                time_pref="morning", duration_min=2, minimal_version="Сделать хотя бы глоток",
            ),
            Habit(
                uid=user.id, catalog_id="stretch_morning", title="Утренняя растяжка",
                spheres_json=json.dumps(["body"]), days_json=json.dumps([1, 2, 3, 4, 5, 6, 7]),
                time_pref="morning", duration_min=10, minimal_version="2 минуты растяжки",
            ),
            Habit(
                uid=user.id, catalog_id="deep_breathing", title="Дыхательная практика",
                spheres_json=json.dumps(["energy", "mind"]), days_json=json.dumps([1, 2, 3, 4, 5, 6, 7]),
                time_pref="evening", duration_min=5, minimal_version="1 минута дыхания",
            ),
        ]
        db.add_all(habits)
        db.commit()
        for h in habits:
            db.refresh(h)
        for offset in range(14, 0, -1):
            log_date = today - timedelta(days=offset)
            for h in habits:
                status = "missed" if offset in (9, 4) else "done"
                log_habit(db, habit_id=h.id, on_date=log_date, status=status, now=datetime.now(timezone.utc))

        # --- Вредная привычка: таймер воздержания + тренд вниз за 14 дней ---
        bad_habit = BadHabit(
            uid=user.id, catalog_id="social_media_scroll", title="Бесцельный скролл соцсетей",
            triggers_json=json.dumps(["boredom", "stress", "automatic", "procrastination"]),
            replacement_id="read_book", baseline_per_day=90.0, target_per_day=30.0, unit="minutes",
        )
        db.add(bad_habit)
        db.commit()
        db.refresh(bad_habit)
        # тренд вниз за 14 дней (офсеты 14..3) — последний срыв в истории
        # оставляем на офсете 2 (2 дня 5 часов назад), чтобы таймер
        # "Держусь" на Главной показывал осмысленное "2 дн 5 ч", а не 0:
        # ничего не логируем на офсетах 1/0 (вчера/сегодня).
        declining_minutes = [85, 80, 75, 70, 68, 60, 58, 50, 45, 42, 38, 35]
        for offset, minutes in zip(range(14, 2, -1), declining_minutes):
            log = log_bad_habit_slip(
                db, bad_habit_id=bad_habit.id, on_date=today - timedelta(days=offset),
                trigger_id="boredom", now=datetime.now(timezone.utc) - timedelta(days=offset),
            )
            log.value = float(minutes)
            db.add(log)
        db.commit()
        last_slip_at = datetime.now(timezone.utc) - timedelta(days=2, hours=5)
        log = log_bad_habit_slip(
            db, bad_habit_id=bad_habit.id, on_date=(today - timedelta(days=2)),
            trigger_id="stress", now=last_slip_at,
        )
        log.value = 20.0
        log.at = last_slip_at
        db.add(log)
        db.commit()

        print(
            f"Готово: {DEMO_LOGIN} (id={user.id}), пароль {DEMO_PASSWORD}. "
            f"Сезоны: body/muscle_gain день {day_num_body}/90, "
            f"mind/deep_focus день {day_num_mind}/60. "
            f"4 активные сферы (body/mind/energy/character), 3 привычки (14 дней), "
            f"1 вредная привычка (14-дневный тренд + таймер ~2 дн 5 ч)."
        )


if __name__ == "__main__":
    main()
