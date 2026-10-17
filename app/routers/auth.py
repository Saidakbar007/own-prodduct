"""
Роуты для регистрации, входа и выхода.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import hash_password, verify_password
from app.database import get_session
from app.models import Level, Registration, User
from app.rendering import render

router = APIRouter()


@router.get("/register")
def register_page(request: Request):
    """Показывает форму регистрации."""
    return render(request, "register.html", {"error": None})


@router.post("/register")
def register_submit(
    request: Request,
    name: str = Form(...),
    age: int = Form(None),
    gender: str = Form(None),
    mail: str = Form(...),
    login: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_session),
):
    """Обрабатывает отправленную форму регистрации."""

    # Проверка совпадения паролей
    if password != password_confirm:
        return render(request, "register.html", {"error": "Пароли не совпадают"})

    # Проверка, что почта или логин уже не заняты
    existing = db.exec(
        select(Registration).where(
            (Registration.mail == mail) | (Registration.login == login)
        )
    ).first()
    if existing:
        return render(request, "register.html", {"error": "Эта почта или логин уже используются"})

    # Создаём запись регистрации (с хешем пароля)
    registration = Registration(
        name=name,
        age=age,
        gender=gender,
        mail=mail,
        login=login,
        password=hash_password(password),
    )
    db.add(registration)
    db.commit()

    # Создаём профиль пользователя
    user = User(mail=mail, login=login, habits=0, goals=0)
    db.add(user)
    db.commit()
    db.refresh(user)

    # Создаём стартовый уровень пользователя
    level = Level(uid=user.id, point=0, name="Новичок")
    db.add(level)
    db.commit()

    # Сразу авторизуем нового пользователя и ведём на короткий онбординг
    request.session["user_id"] = user.id
    return RedirectResponse("/onboarding", status_code=303)


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

    registration = db.exec(
        select(Registration).where(Registration.login == login)
    ).first()

    if not registration or not verify_password(password, registration.password):
        return render(request, "login.html", {"error": "Неверный логин или пароль"})

    user = db.exec(select(User).where(User.login == registration.login)).first()

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/try-demo")
def try_demo(request: Request, db: Session = Depends(get_session)):
    """Входит под демо-аккаунтом в один клик (для кнопки на лендинге)."""
    user = db.exec(select(User).where(User.login == "demo")).first()
    if user:
        request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/logout")
def logout(request: Request):
    """Завершает сессию пользователя."""
    request.session.clear()
    return RedirectResponse("/", status_code=303)
