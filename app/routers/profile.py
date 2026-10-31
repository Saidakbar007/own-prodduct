"""
«Профиль» (§7.9): аватар (3D-герой), полка пройденных сезонов, настройки
(тема, язык, часовой пояс, приватность), выход.
"""

import os
from datetime import datetime, timezone as dt_timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.i18n import translate
from app.models import Proof, Reveal, Season, User
from app.rendering import render
from app.services.flash import push_flash
from app.services.usertime import can_change_timezone, is_valid_timezone

router = APIRouter()

HERO_STAGES = 5
STAGE_ORDINALS = {
    "ru": ["первого", "второго", "третьего", "четвёртого", "пятого"],
    "uz": ["birinchi", "ikkinchi", "uchinchi", "toʻrtinchi", "beshinchi"],
}

# Выпадающий список в профиле — частые пояса для аудитории продукта
# (ru/uz) плюс несколько опорных мировых; текущее значение пользователя
# подмешивается отдельно, даже если его нет в этом списке.
CURATED_TIMEZONES = [
    "UTC",
    "Asia/Tashkent",
    "Asia/Almaty",
    "Asia/Bishkek",
    "Asia/Dushanbe",
    "Asia/Ashgabat",
    "Asia/Baku",
    "Asia/Yekaterinburg",
    "Europe/Moscow",
    "Europe/Kyiv",
    "Europe/Minsk",
    "Asia/Dubai",
    "Europe/Istanbul",
    "Europe/London",
    "Europe/Berlin",
    "America/New_York",
]


def hero_stage_for(completed_count: int) -> int:
    return min(HERO_STAGES, 1 + completed_count)


def hero_caption_for(completed_count: int, lang: str) -> str:
    stage = hero_stage_for(completed_count)
    if stage >= HERO_STAGES:
        return translate(lang, "profile.hero_caption_max")
    ordinals = STAGE_ORDINALS.get(lang, STAGE_ORDINALS["ru"])
    ordinal = ordinals[min(completed_count, len(ordinals) - 1)]
    return translate(lang, "profile.hero_caption_next", ordinal=ordinal)


def timezone_options_for(user: User) -> list[str]:
    options = list(CURATED_TIMEZONES)
    if user.timezone not in options:
        options.append(user.timezone)
    return options


@router.get("/profile")
def profile_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    completed = db.exec(
        select(Season)
        .where(Season.uid == user.id, Season.status == "finished")
        .order_by(Season.created_at.desc())
    ).all()
    reveals = {
        s.id: db.exec(select(Reveal).where(Reveal.season_id == s.id)).first() for s in completed
    }
    stage = hero_stage_for(len(completed))

    return render(
        request,
        "profile.html",
        {
            "user": user,
            "completed": completed,
            "reveals": reveals,
            "hero_stage": stage,
            "hero_caption": hero_caption_for(len(completed), user.language),
            "can_change_timezone": can_change_timezone(user),
            "timezone_options": timezone_options_for(user),
            "lang": user.language,
        },
    )


@router.post("/profile/settings")
def set_settings(
    request: Request,
    language: str = Form(...),
    timezone: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Одна кнопка на все настройки профиля (язык + часовой пояс) — вместо
    двух отдельных форм с двумя "Сохранить" (UX-правка)."""
    if language in ("ru", "uz"):
        user.language = language

    if timezone != user.timezone:
        if not can_change_timezone(user):
            push_flash(request, "profile.error_timezone_cooldown", "error")
        elif is_valid_timezone(timezone):
            user.timezone = timezone
            user.timezone_changed_at = datetime.now(dt_timezone.utc)

    db.add(user)
    db.commit()
    push_flash(request, "profile.settings_saved", "success")
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/delete-photos")
def delete_all_photos(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """§9: кнопка "удалить все мои фото"."""
    proofs = db.exec(select(Proof).where(Proof.uid == user.id)).all()
    for proof in proofs:
        path = os.path.join("uploads", proof.filename)
        if os.path.exists(path):
            os.remove(path)
        db.delete(proof)
    db.commit()
    push_flash(request, "profile.photos_deleted", "success")
    return RedirectResponse("/profile", status_code=303)
