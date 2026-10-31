"""
Роуты для регистрации, входа и выхода.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import hash_password, verify_password
from app.database import get_session
from app.models import User
from app.rendering import render
from app.services.events import log_event_safe
from app.services.flash import push_flash
from app.services.seasons import create_season
from app.services.usertime import DEFAULT_TIMEZONE, is_valid_timezone

router = APIRouter()

MIN_AGE = 18


@router.get("/register")
def register_page(request: Request):
    """Показывает форму регистрации."""
    return render(request, "register.html", {"error": None})


@router.post("/register")
def register_submit(
    request: Request,
    name: str = Form(...),
    birth_year: int = Form(...),
    age_confirm: Optional[str] = Form(None),
    email: str = Form(...),
    login: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    timezone: str = Form(DEFAULT_TIMEZONE),
    db: Session = Depends(get_session),
):
    """Обрабатывает отправленную форму регистрации."""

    if not age_confirm:
        return render(request, "register.html", {"error": "auth.error_age_confirm"})

    if date.today().year - birth_year < MIN_AGE:
        return render(request, "register.html", {"error": "auth.error_age_limit"})

    if password != password_confirm:
        return render(request, "register.html", {"error": "auth.error_password_mismatch"})

    existing = db.exec(
        select(User).where((User.email == email) | (User.login == login))
    ).first()
    if existing:
        return render(request, "register.html", {"error": "auth.error_taken"})

    # Часовой пояс определяется в браузере; на сервере проверяем, что он валиден
    safe_timezone = timezone if is_valid_timezone(timezone) else DEFAULT_TIMEZONE

    draft = request.session.get("onboarding") or {}

    user = User(
        name=name,
        birth_year=birth_year,
        email=email,
        login=login,
        password_hash=hash_password(password),
        timezone=safe_timezone,
        height_cm=draft.get("height_cm"),
        telegram_user_id=request.session.get("telegram_pending_id"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session.pop("telegram_pending_id", None)
    request.session.pop("telegram_pending_name", None)

    request.session["user_id"] = user.id
    push_flash(request, "auth.welcome_flash", "success")
    log_event_safe(db, "signup", uid=user.id)

    if draft.get("template_id") and "baseline_value" in draft and "length_days" in draft:
        season = create_season(
            db,
            uid=user.id,
            template_id=draft["template_id"],
            length_days=draft["length_days"],
            baseline_value=draft["baseline_value"],
            reference_date=date.today(),
            secondary_baseline_value=draft.get("secondary_baseline_value"),
        )
        log_event_safe(db, "season_started", uid=user.id, season_id=season.id)
        request.session.pop("onboarding", None)
        request.session["current_season_id"] = season.id
        return RedirectResponse("/today?tour=1", status_code=303)

    return RedirectResponse("/", status_code=303)


@router.get("/login")
def login_page(request: Request):
    """Показывает форму входа."""
    return render(request, "login.html", {"error": None})


@router.post("/login")
def login_submit(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_session),
):
    """Проверяет логин и пароль, при успехе открывает сессию."""

    user = db.exec(select(User).where(User.login == login)).first()
    if not user or not verify_password(password, user.password_hash):
        return render(request, "login.html", {"error": "auth.error_invalid_credentials"})

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    """Завершает сессию пользователя."""
    request.session.clear()
    return RedirectResponse("/", status_code=303)
