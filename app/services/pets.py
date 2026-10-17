"""
Питомец героя (v6b): яйцо появляется на 3-м уровне героя, вид выбирается
при вылуплении. Стадия растёт по лучшей ТЕКУЩЕЙ серии пользователя (across
всех привычек) и не откатывается — настроение (весело/грустно) отдельно от
стадии (см. DECISIONS.md, п.8).
"""

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import Pet, User

PET_SPECIES = {"fox": "Лис", "owl": "Сова", "drake": "Дракончик"}

HATCH_MIN_HERO_LEVEL = 3
MAX_STAGE = 5

# Стадия 1..5 по порогам серии дней: 0, 7, 30, 100, 365
STAGE_STREAK_THRESHOLDS = [0, 7, 30, 100, 365]

# Настроение грустнеет только если питомец уже бывал хотя бы на стадии 2+
# (то есть серия уже была нормальной) и серия сейчас полностью прервана.
SAD_MIN_EVER_STAGE = 2


def _now() -> datetime:
    return datetime.now(timezone.utc)


def stage_for_streak(streak: int) -> int:
    """Стадия 1-5 по текущей серии дней (0/7/30/100/365)."""
    stage = 1
    for i, threshold in enumerate(STAGE_STREAK_THRESHOLDS):
        if streak >= threshold:
            stage = i + 1
    return min(stage, MAX_STAGE)


def can_hatch(hero_level: int) -> bool:
    return hero_level >= HATCH_MIN_HERO_LEVEL


def get_or_create_pet(db: Session, uid: int) -> Pet:
    pet = db.exec(select(Pet).where(Pet.uid == uid)).first()
    if pet:
        return pet
    pet = Pet(uid=uid, species=None, best_stage_reached=1)
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def hatch_pet(db: Session, user: User, hero_level: int, species: str) -> tuple[bool, str]:
    """Выбирает вид питомца при вылуплении — только раз, когда ур. героя >= 3."""
    if not can_hatch(hero_level):
        return False, f"Питомец вылупится с {HATCH_MIN_HERO_LEVEL}-го уровня героя"
    if species not in PET_SPECIES:
        return False, "Неизвестный вид питомца"

    pet = get_or_create_pet(db, user.id)
    if pet.species:
        return False, "Питомец уже вылупился"

    pet.species = species
    pet.hatched_at = _now()
    db.add(pet)
    db.commit()
    return True, f"{PET_SPECIES[species]} вылупился!"


def sync_pet_stage(db: Session, user: User, current_streak: int) -> Pet:
    """
    Обновляет лучшую стадию питомца по текущей серии — стадия не
    откатывается, поэтому только повышаем `best_stage_reached`.
    """
    pet = get_or_create_pet(db, user.id)
    current_stage = stage_for_streak(current_streak)
    if current_stage > pet.best_stage_reached:
        pet.best_stage_reached = current_stage
        db.add(pet)
        db.commit()
        db.refresh(pet)
    return pet


def pet_mood(pet: Pet, current_streak: int) -> str:
    """Весело, если серия жива или питомец ещё не доходил до нормальной стадии; иначе грустно."""
    if current_streak == 0 and pet.best_stage_reached >= SAD_MIN_EVER_STAGE:
        return "грустно"
    return "весело"


def pet_profile(db: Session, user: User, hero_level: int, current_streak: int) -> dict:
    """Собирает всё для отображения питомца на /hero и на главной."""
    pet = sync_pet_stage(db, user, current_streak)
    return {
        "egg": pet.species is None,
        "can_hatch": can_hatch(hero_level) and pet.species is None,
        "species": pet.species,
        "species_name": PET_SPECIES.get(pet.species),
        "stage": pet.best_stage_reached,
        "current_stage": stage_for_streak(current_streak),
        "mood": pet_mood(pet, current_streak) if pet.species else None,
        "hero_level": hero_level,
        "hatch_min_level": HATCH_MIN_HERO_LEVEL,
    }
