"""
«Серия» (§7.5) и Reveal (§7.8): веб-страница + PNG-карточка для сторис.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse, Response
from starlette.requests import Request
from sqlmodel import Session, select

import os

from app.auth import require_user
from app.database import get_session
from app.models import Season, User
from app.rendering import render
from app.services import mascot
from app.services.cards import CARDS_DIR, save_card
from app.services.episodes import episode_card_png, get_or_create_episode
from app.services.reveals import get_or_create_reveal, reveal_card_png
from app.services.seasons import sync_season_state
from app.services.usertime import today_for

router = APIRouter()


def _own_season(db: Session, season_id: int, user: User) -> Season:
    season = db.get(Season, season_id)
    if not season or season.uid != user.id:
        raise HTTPException(status_code=404)
    return season


@router.get("/season/{season_id}/episode/{week_number}")
def episode_page(
    season_id: int,
    week_number: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = _own_season(db, season_id, user)
    episode = get_or_create_episode(db, season, week_number)
    if not episode:
        raise HTTPException(status_code=404)
    return render(
        request,
        "episode.html",
        {"season": season, "episode": episode, "lang": user.language},
    )


@router.get("/season/{season_id}/episode/{week_number}/card.png")
def episode_card(
    season_id: int,
    week_number: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = _own_season(db, season_id, user)
    episode = get_or_create_episode(db, season, week_number)
    if not episode:
        raise HTTPException(status_code=404)

    if episode.card_image_path and os.path.exists(episode.card_image_path):
        with open(episode.card_image_path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")

    png_bytes = episode_card_png(season, episode)
    episode.card_image_path = save_card(png_bytes, CARDS_DIR, f"episode-{episode.id}.png")
    db.add(episode)
    db.commit()
    return Response(content=png_bytes, media_type="image/png")


@router.get("/season/{season_id}/reveal")
def reveal_page(
    season_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = _own_season(db, season_id, user)
    today = today_for(user)
    season = sync_season_state(db, season, today)
    if season.status != "finished":
        return RedirectResponse("/today", status_code=303)

    reveal = get_or_create_reveal(db, season)
    mascot_event = f"reveal_{reveal.tier}"

    return render(
        request,
        "reveal.html",
        {
            "season": season,
            "reveal": reveal,
            "mascot_phrase": mascot.phrase_for(mascot_event, user.language),
            "lang": user.language,
        },
    )


@router.get("/season/{season_id}/reveal/card.png")
def reveal_card(
    season_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = _own_season(db, season_id, user)
    reveal = get_or_create_reveal(db, season)

    if reveal.card_image_path and os.path.exists(reveal.card_image_path):
        with open(reveal.card_image_path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")

    png_bytes = reveal_card_png(season, reveal, next_season_label="Новый сезон")
    reveal.card_image_path = save_card(png_bytes, CARDS_DIR, f"reveal-{reveal.id}.png")
    db.add(reveal)
    db.commit()
    return Response(content=png_bytes, media_type="image/png")


@router.post("/season/{season_id}/next")
def next_season(
    season_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    """«Следующий сезон» (§7.8) — в Фазе 2 просто ведёт обратно в онбординг
    (выбор следующего уровня той же цели или новой — делает человек сам)."""
    _own_season(db, season_id, user)
    return RedirectResponse("/onboarding", status_code=303)
