"""
«Я» (§12, §14 NewLife v8; было «Профиль» §7.9 Сезонов): аватар (3D-герой),
полка пройденных сезонов, колесо жизни, режим и обязательные дела,
настройки, «Методы NewLife», «Откуда эти нормы», «О NewLife», выход.
"""

import json
import os
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from sqlmodel import Session, select

from app.auth import get_current_user, require_user, verify_password
from app.database import get_session
from app.i18n import translate
from app.models import Commitment, Profile, Proof, Reveal, Season, SphereLevelHistory, SphereState, User
from app.newlife.goal_catalog import all_goals
from app.newlife.methods import METHODS
from app.newlife.question_bank import question_by_id
from app.newlife.spheres import SPHERE_BY_ID, SPHERES
from app.rendering import render
from app.services.data_privacy import delete_user_account, export_user_data
from app.services.day_questions import recent_answers
from app.services.flash import push_flash
from app.services.newlife_onboarding import WEEKDAY_LABELS
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

    profile = db.exec(select(Profile).where(Profile.uid == user.id)).first()
    sphere_states = db.exec(
        select(SphereState).where(SphereState.uid == user.id, SphereState.active.is_(True))
    ).all()
    wheel = [
        {"sphere": SPHERE_BY_ID[s.sphere_id], "level": s.level}
        for s in sphere_states
        if s.sphere_id in SPHERE_BY_ID
    ]
    commitments = db.exec(select(Commitment).where(Commitment.uid == user.id, Commitment.active.is_(True))).all()
    day_answers = [
        {"question_text": q.text, "option_text": a.option_text, "answered_on": a.answered_on}
        for a in recent_answers(db, user.id, limit=5)
        if (q := question_by_id(a.question_id))
    ]

    return render(
        request,
        "profile.html",
        {
            "user": user,
            "profile": profile,
            "wheel": wheel,
            "commitments_count": len(commitments),
            "day_answers": day_answers,
            "completed": completed,
            "reveals": reveals,
            "hero_stage": stage,
            "hero_caption": hero_caption_for(len(completed), user.language),
            "can_change_timezone": can_change_timezone(user),
            "timezone_options": timezone_options_for(user),
            "lang": user.language,
        },
    )


@router.get("/profile/wheel")
def wheel_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    states = {s.sphere_id: s for s in db.exec(select(SphereState).where(SphereState.uid == user.id)).all()}
    rows = []
    for sphere in SPHERES:
        state = states.get(sphere.id)
        rows.append({"sphere": sphere, "level": state.level if state else None, "active": bool(state and state.active)})
    return render(request, "profile_wheel.html", {"rows": rows, "lang": user.language})


@router.post("/profile/wheel/{sphere_id}/level")
def adjust_sphere_level(
    sphere_id: str,
    delta: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    if sphere_id not in SPHERE_BY_ID:
        return RedirectResponse("/profile/wheel", status_code=303)
    state = db.exec(select(SphereState).where(SphereState.uid == user.id, SphereState.sphere_id == sphere_id)).first()
    if not state:
        state = SphereState(uid=user.id, sphere_id=sphere_id, level=4, priority=2, active=True)
    state.level = max(1, min(10, state.level + delta))
    state.updated_at = datetime.now(dt_timezone.utc)
    db.add(state)
    db.add(SphereLevelHistory(uid=user.id, sphere_id=sphere_id, level=state.level))
    db.commit()
    return RedirectResponse("/profile/wheel", status_code=303)


@router.get("/profile/commitments")
def commitments_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    commitments = db.exec(select(Commitment).where(Commitment.uid == user.id, Commitment.active.is_(True))).all()
    return render(
        request,
        "profile_commitments.html",
        {"commitments": commitments, "weekday_labels": WEEKDAY_LABELS, "lang": user.language},
    )


@router.post("/profile/commitments/{commitment_id}/remove")
def remove_commitment(commitment_id: int, user: User = Depends(require_user), db: Session = Depends(get_session)):
    c = db.get(Commitment, commitment_id)
    if c and c.uid == user.id:
        c.active = False
        db.add(c)
        db.commit()
    return RedirectResponse("/profile/commitments", status_code=303)


@router.get("/methods")
def methods_page(request: Request, user: User = Depends(require_user)):
    return render(request, "methods.html", {"methods": METHODS, "lang": user.language})


@router.get("/sources")
def sources_page(request: Request, user: User = Depends(require_user)):
    seen = set()
    sources = []
    for goal in all_goals():
        if goal.source.is_heuristic or goal.source.name in seen:
            continue
        seen.add(goal.source.name)
        sources.append({"source": goal.source.name, "source_url": goal.source.url, "safe_rate": goal.pace})
    return render(request, "sources.html", {"sources": sources, "lang": user.language})


@router.get("/about")
def about_page(request: Request, user: User = Depends(require_user)):
    return render(request, "about.html", {"lang": user.language})


@router.get("/help")
def help_page(request: Request, user: User = Depends(get_current_user)):
    """Экран помощи (PRD 1.0 «Безопасность»): 103/112 — общеизвестные номера
    скорой и экстренных служб Узбекистана, встроены всегда. Линия
    психологической помощи — из HELPLINE_UZ (.env); без неё строка просто
    не показывается, чтобы не вывести на экран непроверенный номер.
    БЕЗ обязательного входа (get_current_user, не require_user) — номера
    должны быть доступны сразу, в т.ч. во время онбординга до регистрации
    и при мыслях о самоповреждении (NEWLIFE_1_0_CONTENT.md §6 п.7)."""
    return render(
        request,
        "help.html",
        {"helpline_uz": os.getenv("HELPLINE_UZ") or None, "lang": user.language if user else "ru"},
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


@router.get("/profile/export")
def export_data(user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Экспорт всех своих данных в JSON (PRD 1.0 «Безопасность и данные») —
    app/services/data_privacy.py, дженерик по всем таблицам с uid."""
    data = export_user_data(db, user.id)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="newlife-export-{user.id}.json"'},
    )


@router.get("/profile/delete-account")
def delete_account_form(request: Request, user: User = Depends(require_user)):
    return render(request, "profile_delete_account.html", {"error": None, "lang": user.language})


@router.post("/profile/delete-account")
def delete_account_submit(
    request: Request,
    password: str = Form(...),
    confirm: str = Form(""),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """Удаление аккаунта (PRD 1.0 «Безопасность и данные») — требует пароль
    и явное подтверждение чекбоксом, необратимо, удаляет ВСЕ данные
    (app/services/data_privacy.py::delete_user_account)."""
    if not verify_password(password, user.password_hash) or confirm != "1":
        return render(
            request,
            "profile_delete_account.html",
            {"error": "profile.delete_account_error", "lang": user.language},
        )
    delete_user_account(db, user.id)
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@router.get("/privacy")
def privacy_page(request: Request, user: Optional[User] = Depends(get_current_user)):
    return render(request, "privacy.html", {"lang": user.language if user else "ru"})
