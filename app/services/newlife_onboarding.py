"""
Константы и мелкая логика экранов 6-11 онбординга NewLife v8 (§5): режим дня,
время на себя, когда больше сил, ограничения, WOOP. Чистые данные — без
обращения к БД, чтобы роутер и тесты могли их переиспользовать напрямую.
"""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session

from app.models import Commitment, Profile, SphereState

# Экран 6: время шагом 30 минут.
WAKE_TIME_OPTIONS = ["05:00", "05:30", "06:00", "06:30", "07:00", "07:30", "08:00", "09:00"]
SLEEP_TIME_OPTIONS = ["21:00", "21:30", "22:00", "22:30", "23:00", "23:30", "00:00", "01:00"]

# Экран 8: сколько времени в день готов на себя.
DAILY_MINUTES_OPTIONS = [15, 30, 60, 90]

# Экран 9: когда больше сил (chronotype).
CHRONOTYPE_OPTIONS = ["morning", "day", "evening", "varies"]

# Экран 10: ограничения, мультивыбор.
CONSTRAINT_OPTIONS = [
    "no_gym",
    "has_pullup_bar",
    "has_dumbbells",
    "joint_pain",
    "back_pain",
    "low_budget",
]

# Экран 11 (WOOP): "что чаще всего мешало?"
OBSTACLE_OPTIONS = ["tired", "no_time", "forget", "phone", "quit_after_week"]

# WOOP §11: препятствие -> варианты плана "если это случится — что сделаем".
# Ключ плана (первый вариант каждого препятствия) — безопасное значение по
# умолчанию при пропуске.
WOOP_PLANS: dict[str, list[str]] = {
    "tired": ["minimal_2min", "reminder", "anchor"],
    "no_time": ["minimal_2min", "anchor", "reminder"],
    "forget": ["reminder", "anchor", "minimal_2min"],
    "phone": ["remove_phone", "reminder", "minimal_2min"],
    "quit_after_week": ["anchor", "reminder", "minimal_2min"],
}

# Обязательные дела (экран 7): категории.
COMMITMENT_CATEGORIES = ["study", "work", "commute", "family", "religion", "other"]
WEEKDAY_LABELS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def has_completed_profile(profile: Optional[Profile]) -> bool:
    return profile is not None and profile.onboarding_done_at is not None


def create_profile_from_draft(db: Session, uid: int, draft: dict) -> Profile:
    """Сохраняет точку А из черновика онбординга (session["onboarding"]) при
    регистрации: Profile, SphereState на каждую выбранную сферу, Commitment
    на каждое обязательное дело. Вызывается один раз, сразу после создания
    пользователя — до этого в БД ничего не попадало (§5)."""
    profile = Profile(
        uid=uid,
        height_cm=draft.get("height_cm"),
        weight_kg=draft.get("weight_kg"),
        wake_time=draft.get("wake_time"),
        sleep_time=draft.get("sleep_time"),
        chronotype=draft.get("chronotype"),
        daily_minutes=draft.get("daily_minutes"),
        constraints_json=json.dumps(draft.get("constraints", [])),
        main_obstacle=draft.get("main_obstacle"),
        has_medical_diagnosis=draft.get("has_medical_diagnosis"),
        is_pregnant=draft.get("is_pregnant"),
        disordered_eating_signal=draft.get("disordered_eating_signal"),
        onboarding_done_at=datetime.now(timezone.utc),
    )
    db.add(profile)

    levels = draft.get("sphere_levels", {})
    for sphere_id in draft.get("spheres", []):
        db.add(
            SphereState(
                uid=uid,
                sphere_id=sphere_id,
                level=levels.get(sphere_id, 4),
                priority=2,
                active=True,
            )
        )

    for c in draft.get("commitments", []):
        db.add(
            Commitment(
                uid=uid,
                title=c["title"],
                category=c["category"],
                weekdays_json=json.dumps(c["weekdays"]),
                start_time=c["start_time"],
                end_time=c["end_time"],
            )
        )

    db.commit()
    db.refresh(profile)
    return profile
