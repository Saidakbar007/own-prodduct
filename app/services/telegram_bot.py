"""
Логика бота (§12 ТЗ): напоминание о действии дня в выбранное время,
кнопки "Сделал"/"Минимум"/"Не получится" прямо в сообщении, напоминания
о замере и выходе серии, реплики ведущего, ссылка на Reveal. Тихие часы
23:00-08:00. Без дублей — see SeasonDay.reminder_sent.
"""

import logging
import os
from datetime import datetime, time, timezone
from typing import Optional

from sqlmodel import Session, select

from app.models import SeasonDay, User
from app.services import mascot
from app.services.seasons import get_active_season, get_day, today_day_number
from app.services.telegram_api import answer_callback_query, send_message
from app.services.usertime import now_for, today_for

QUIET_HOURS_START = time(23, 0)
QUIET_HOURS_END = time(8, 0)


def is_quiet_hours(moment_time: time) -> bool:
    """23:00-08:00 — интервал, переходящий через полночь."""
    if QUIET_HOURS_START <= QUIET_HOURS_END:
        return QUIET_HOURS_START <= moment_time < QUIET_HOURS_END
    return moment_time >= QUIET_HOURS_START or moment_time < QUIET_HOURS_END


def app_base_url() -> str:
    """APP_BASE_URL — ручной override; иначе RENDER_EXTERNAL_URL, который
    Render сам подставляет каждому веб-сервису (публичный https-адрес)."""
    return os.getenv("APP_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL", "")


def open_app_keyboard() -> dict:
    url = app_base_url()
    if not url:
        return {}
    return {"inline_keyboard": [[{"text": "Открыть Сезоны", "web_app": {"url": url}}]]}


def action_keyboard(season_id: int) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Сделал", "callback_data": f"done:{season_id}"},
                {"text": "➖ Минимум", "callback_data": f"minimal:{season_id}"},
                {"text": "🚫 Не получится", "callback_data": f"skip:{season_id}"},
            ]
        ]
    }


# --------------------------------------------------------------- webhook

def handle_update(db: Session, update: dict) -> None:
    """Никогда не падает наружу: сбой при отправке ответа в Telegram API
    (сеть, недоступность) не должен возвращать вебхуку ошибку — Telegram
    будет повторять доставку того же update, плодя дубли."""
    try:
        if "message" in update:
            _handle_message(db, update["message"])
        elif "callback_query" in update:
            _handle_callback(db, update["callback_query"])
    except Exception:
        logging.getLogger("sezony.telegram").exception("failed to handle telegram update")


def _handle_message(db: Session, message: dict) -> None:
    text = (message.get("text") or "").strip()
    chat_id = message["chat"]["id"]

    if text.startswith("/start"):
        send_message(
            chat_id,
            "Привет! Я веду сезон вместе с тобой. Открой приложение, чтобы начать "
            "или продолжить — через кнопку ниже или меню чата.",
            reply_markup=open_app_keyboard() or None,
        )
        return

    # Остальной текст бот не разбирает — всё взаимодействие через Mini App и кнопки.
    send_message(chat_id, "Не понял команду. Открой приложение через меню чата.")


def _handle_callback(db: Session, callback: dict) -> None:
    data = callback.get("data", "")
    chat_id = callback["message"]["chat"]["id"]
    tg_user_id = callback["from"]["id"]
    callback_id = callback["id"]

    user = db.exec(select(User).where(User.telegram_user_id == tg_user_id)).first()
    if not user:
        answer_callback_query(callback_id, "Сначала войди через приложение")
        return

    action, _, season_id_str = data.partition(":")
    season = get_active_season(db, user.id)
    if not season or str(season.id) != season_id_str:
        answer_callback_query(callback_id, "Этот сезон уже неактивен")
        return

    today = today_for(user)
    day_number = today_day_number(season, today)
    day = get_day(db, season.id, day_number)
    if not day or day.status != "planned":
        answer_callback_query(callback_id, "Уже отмечено сегодня")
        return

    if action == "done":
        day.status = "done"
        event = "done"
    elif action == "minimal":
        day.status = "minimal"
        event = "minimal"
    elif action == "skip":
        answer_callback_query(callback_id, mascot.phrase_for("skip", user.language))
        return
    else:
        answer_callback_query(callback_id, "Не понял")
        return

    day.done_at = datetime.now(timezone.utc)
    db.add(day)
    db.commit()

    phrase = mascot.phrase_for(event, user.language)
    answer_callback_query(callback_id, phrase[:200])
    send_message(chat_id, phrase)


# ------------------------------------------------------------- напоминания

def due_reminder_users(db: Session, within_minute: Optional[datetime] = None) -> list[User]:
    """Пользователи, которым сейчас (по их локальному времени, с точностью
    до минуты) пора напомнить — не в тихие часы."""
    candidates = db.exec(
        select(User).where(User.reminder_time.is_not(None), User.telegram_user_id.is_not(None))
    ).all()
    due = []
    for user in candidates:
        local_now = now_for(user)
        if is_quiet_hours(local_now.time()):
            continue
        try:
            hh, mm = (int(part) for part in user.reminder_time.split(":"))
        except (ValueError, AttributeError):
            continue
        if local_now.hour == hh and local_now.minute == mm:
            due.append(user)
    return due


def send_daily_reminder(db: Session, user: User) -> bool:
    """Отправляет напоминание о действии дня — не дублирует (reminder_sent)."""
    season = get_active_season(db, user.id)
    if not season:
        return False

    today = today_for(user)
    day_number = today_day_number(season, today)
    day = get_day(db, season.id, day_number)
    if not day or day.status != "planned" or day.reminder_sent:
        return False

    event = "wave_start" if day_number == 1 else "done"
    phrase = mascot.phrase_for(event, user.language)
    text = f"{day.title}\n\n{phrase}"
    send_message(user.telegram_user_id, text, reply_markup=action_keyboard(season.id))

    day.reminder_sent = True
    db.add(day)
    db.commit()
    return True


def run_due_reminders(db: Session) -> int:
    """Вызывается фоновым циклом раз в минуту (app.main) — отправляет всем,
    кому сейчас время, и возвращает число отправленных напоминаний."""
    sent = 0
    for user in due_reminder_users(db):
        try:
            if send_daily_reminder(db, user):
                sent += 1
        except Exception:
            continue
    return sent
