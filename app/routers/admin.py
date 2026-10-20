"""
Админка (v6d): только для логинов из ADMIN_LOGINS (require_admin — 404
для всех остальных). /admin — общая точка входа со ссылками на галерею
ассетов и песочницу своего аккаунта.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlmodel import Session, select

from app.auth import require_admin
from app.database import get_session
from app.models import Level, Pet, User
from app.rendering import render
from app.services.flash import push_flash
from app.services.gallery import build_gallery
from app.services.levels import level_progress
from app.services.pets import PET_SPECIES, get_or_create_pet
from app.services.sandbox import (
    PRESET_LABELS,
    PRESETS,
    apply_preset,
    boss_finish,
    boss_hit,
    grant_all_achievements,
    grant_all_items,
    open_chest_of_rarity,
    reset_to_snapshot,
    run_council_now,
    set_coins,
    set_hero_level,
    set_pet,
    set_sphere,
    set_streak,
    set_trust_score,
)
from app.services.personas import PERSONAS, persona_profile
from app.services.shop import RARITY_ORDER
from app.services.spheres import MAX_LEVEL as SPHERE_MAX_LEVEL
from app.services.streak import best_streak_for_user

router = APIRouter()

SPHERE_STATES = ["активна", "дремлет", "спит"]


def _sandbox_context(db: Session, user: User, error: str = None) -> dict:
    level = db.exec(select(Level).where(Level.uid == user.id)).first()
    progress = level_progress(level.point if level else 0)
    pet = get_or_create_pet(db, user.id)
    return {
        "user": user,
        "error": error,
        "hero_level": progress["level"],
        "personas": persona_profile(db, user.id),
        "sphere_max_level": SPHERE_MAX_LEVEL,
        "sphere_states": SPHERE_STATES,
        "streak": best_streak_for_user(db, user.id),
        "pet": pet,
        "pet_species": PET_SPECIES,
        "rarities": RARITY_ORDER,
        "presets": [{"code": p, "label": PRESET_LABELS[p]} for p in PRESETS],
    }


@router.get("/admin")
def admin_home(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    return render(request, "admin/index.html", {"user": user}, db=db, user=user)


@router.get("/admin/gallery")
def admin_gallery(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    gallery = build_gallery(db)
    return render(request, "admin/gallery.html", {"user": user, "gallery": gallery}, db=db, user=user)


@router.get("/admin/sandbox")
def admin_sandbox(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    return render(request, "admin/sandbox.html", _sandbox_context(db, user), db=db, user=user)


@router.post("/admin/sandbox/apply")
async def admin_sandbox_apply(
    request: Request,
    hero_level: int = Form(...),
    streak_days: int = Form(...),
    coins: int = Form(...),
    trust_score: int = Form(...),
    pet_species: str = Form(""),
    pet_stage: int = Form(1),
    user: User = Depends(require_admin),
    db: Session = Depends(get_session),
):
    form = await request.form()
    set_hero_level(db, user, hero_level)
    for code in PERSONAS:
        sphere_level_value = int(form.get(f"{code}_level", 1))
        sphere_state_value = form.get(f"{code}_state", "активна")
        set_sphere(db, user, code, sphere_level_value, sphere_state_value)
    set_streak(db, user, streak_days)
    set_pet(db, user, pet_species or None, pet_stage)
    set_coins(db, user, coins)
    set_trust_score(db, user, trust_score)
    push_flash(request, "Применено")
    return render(request, "admin/sandbox.html", _sandbox_context(db, user), db=db, user=user)


@router.post("/admin/sandbox/grant-items")
def admin_sandbox_grant_items(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    count = grant_all_items(db, user)
    push_flash(request, f"Выдано предметов: {count}")
    return render(request, "admin/sandbox.html", _sandbox_context(db, user), db=db, user=user)


@router.post("/admin/sandbox/grant-achievements")
def admin_sandbox_grant_achievements(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    count = grant_all_achievements(db, user)
    push_flash(request, f"Выдано достижений: {count}")
    return render(request, "admin/sandbox.html", _sandbox_context(db, user), db=db, user=user)


@router.post("/admin/sandbox/open-chest")
def admin_sandbox_open_chest(
    request: Request, rarity: str = Form(...), user: User = Depends(require_admin), db: Session = Depends(get_session)
):
    chest = open_chest_of_rarity(db, user, rarity)
    push_flash(request, f"Сундук открыт: {chest.reward_value}")
    return render(request, "admin/sandbox.html", _sandbox_context(db, user), db=db, user=user)


@router.post("/admin/sandbox/council")
def admin_sandbox_council(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    run_council_now(db, user)
    push_flash(request, "Совет недели запущен")
    return render(request, "admin/sandbox.html", _sandbox_context(db, user), db=db, user=user)


@router.post("/admin/sandbox/boss-damage")
def admin_sandbox_boss_damage(
    request: Request, amount: int = Form(20), user: User = Depends(require_admin), db: Session = Depends(get_session)
):
    boss_hit(db, user, amount)
    push_flash(request, f"Нанесено {amount} урона боссу")
    return render(request, "admin/sandbox.html", _sandbox_context(db, user), db=db, user=user)


@router.post("/admin/sandbox/boss-defeat")
def admin_sandbox_boss_defeat(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    boss_finish(db, user)
    push_flash(request, "Босс недели побеждён")
    return render(request, "admin/sandbox.html", _sandbox_context(db, user), db=db, user=user)


@router.post("/admin/sandbox/preset")
def admin_sandbox_preset(
    request: Request, preset: str = Form(...), user: User = Depends(require_admin), db: Session = Depends(get_session)
):
    message = apply_preset(db, user, preset)
    push_flash(request, message)
    return render(request, "admin/sandbox.html", _sandbox_context(db, user), db=db, user=user)


@router.post("/admin/sandbox/reset")
def admin_sandbox_reset(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    ok = reset_to_snapshot(db, user)
    push_flash(request, "Прогресс восстановлен" if ok else "Нет снимка — ничего не меняли", "success" if ok else "error")
    return render(request, "admin/sandbox.html", _sandbox_context(db, user), db=db, user=user)
