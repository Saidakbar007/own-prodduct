"""
Страница /hero: герой (стадия по рангу), пятиугольник сфер, 5 карточек
личностей с уровнем/стадией/состоянием и последней репликой коуча.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.models import CoachMessage, Level, User
from app.rendering import render
from app.routers.habits import best_streak_with_freeze_for_user
from app.services.flash import push_flash
from app.services.game_assets import hero_image_url, persona_image_url, pet_image_url
from app.services.levels import level_progress
from app.services.pentagon import pentagon_chart
from app.services.personas import PERSONA_IMAGE_CODE, persona_profile
from app.services.persona_voices import balance_warning_line, greeting_line
from app.services.pets import PET_SPECIES, hatch_pet, pet_profile
from app.services.spheres import all_spheres_progress
from app.services.usertime import local_date, today_for

router = APIRouter()


def _latest_persona_message(db: Session, uid: int, persona_code: str) -> CoachMessage | None:
    return db.exec(
        select(CoachMessage)
        .where(CoachMessage.uid == uid, CoachMessage.persona_code == persona_code, CoachMessage.role == "coach")
        .order_by(CoachMessage.time.desc())
    ).first()


def _ensure_daily_greeting(db: Session, user: User, leading_code: str) -> None:
    """Приветствие от ведущей личности — не чаще раза в календарный день (по поясу пользователя)."""
    latest = _latest_persona_message(db, user.id, leading_code)
    if latest and local_date(user, latest.time) == today_for(user):
        return

    db.add(CoachMessage(uid=user.id, role="coach", text=greeting_line(leading_code), persona_code=leading_code))
    db.commit()


@router.get("/hero")
def hero_page(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    progress = level_progress(level.point if level else 0)

    profile = persona_profile(db, user.id)
    leading_code = next((p["sphere_code"] for p in profile if p["is_leading"]), profile[0]["sphere_code"])
    _ensure_daily_greeting(db, user, leading_code)

    cards = []
    for persona in profile:
        code = persona["sphere_code"]
        image_code = PERSONA_IMAGE_CODE[code]
        if persona["state"] == "спит":
            last_line = balance_warning_line(code, persona["days_since_activity"] or 0)
        else:
            message = _latest_persona_message(db, user.id, code)
            last_line = message.text if message else "Пока нет новостей — начни с отметки привычки."
        cards.append(
            {
                **persona,
                "image_url": persona_image_url(image_code, persona["stage"]),
                "last_line": last_line,
            }
        )

    pet = pet_profile(db, user, progress["level"], best_streak_with_freeze_for_user(db, user))
    if pet["species"]:
        pet["image_url"] = pet_image_url(pet["species"], pet["stage"])

    return render(
        request,
        "hero.html",
        {
            "user": user,
            "hero_level": progress["level"],
            "hero_rank": progress["rank"],
            "hero_stage": progress["stage"],
            "hero_image_url": hero_image_url(progress["stage"]),
            "hero_chart": pentagon_chart(all_spheres_progress(db, user.id)),
            "personas": cards,
            "pet": pet,
            "pet_species_options": PET_SPECIES,
        },
        db=db,
        user=user,
    )


@router.post("/pet/hatch")
def pet_hatch_route(
    request: Request,
    species: str = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    hero_level = level_progress(level.point if level else 0)["level"]

    ok, message = hatch_pet(db, user, hero_level, species)
    push_flash(request, message, "success" if ok else "error")

    return hero_page(request, user, db)
