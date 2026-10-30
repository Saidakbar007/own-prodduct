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
from app.models import Proof, Season, SeasonDay, User
from app.rendering import render
from app.services import mascot
from app.services.cards import CARDS_DIR, save_card
from app.services.episodes import episode_card_png, get_or_create_episode
from app.services.events import log_event_safe
from app.services.reveals import get_or_create_reveal, reveal_card_png
from app.services.seasons import sync_season_state
from app.services.usertime import today_for
from app.services.video import ffmpeg_available, render_reveal_video

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
    log_event_safe(db, "episode_viewed", uid=user.id, season_id=season.id)
    return render(
        request,
        "episode.html",
        {"season": season, "episode": episode, "lang": user.language},
    )


@router.get("/season/{season_id}/episode/{week_number}/card.png")
def episode_card(
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

    if request.query_params.get("share"):
        log_event_safe(db, "card_shared", uid=user.id, season_id=season.id)

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
    log_event_safe(db, "reveal_viewed", uid=user.id, season_id=season.id)
    mascot_event = f"reveal_{reveal.tier}"

    proof_ids = db.exec(
        select(SeasonDay.proof_id).where(SeasonDay.season_id == season.id, SeasonDay.proof_id.is_not(None))
    ).all()
    has_video = ffmpeg_available() and bool(proof_ids)

    return render(
        request,
        "reveal.html",
        {
            "season": season,
            "reveal": reveal,
            "mascot_phrase": mascot.phrase_for(mascot_event, user.language),
            "has_video": has_video,
            "lang": user.language,
        },
    )


def _day_proof_paths(db: Session, season: Season) -> list[str]:
    """Фото-доказательства дней (§9: не фото тела — те только в Measurement
    с явным photo_pose, сюда не попадают)."""
    proof_ids = db.exec(
        select(SeasonDay.proof_id)
        .where(SeasonDay.season_id == season.id, SeasonDay.proof_id.is_not(None))
        .order_by(SeasonDay.day_number)
    ).all()
    paths = []
    for proof_id in proof_ids:
        proof = db.get(Proof, proof_id)
        if proof:
            path = os.path.join("uploads", proof.filename)
            if os.path.exists(path):
                paths.append(path)
    return paths


@router.get("/season/{season_id}/reveal/video.mp4")
def reveal_video(
    season_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = _own_season(db, season_id, user)
    reveal = get_or_create_reveal(db, season)

    if reveal.video_path and os.path.exists(reveal.video_path):
        with open(reveal.video_path, "rb") as f:
            return Response(content=f.read(), media_type="video/mp4")

    frames = _day_proof_paths(db, season)
    if not frames or not ffmpeg_available():
        raise HTTPException(status_code=404)

    output_path = os.path.join(CARDS_DIR, f"reveal-{reveal.id}.mp4")
    os.makedirs(CARDS_DIR, exist_ok=True)
    result = render_reveal_video(frames, output_path)
    if not result:
        raise HTTPException(status_code=404)

    reveal.video_path = result
    db.add(reveal)
    db.commit()
    with open(result, "rb") as f:
        return Response(content=f.read(), media_type="video/mp4")


@router.get("/season/{season_id}/reveal/card.png")
def reveal_card(
    season_id: int,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_session),
):
    season = _own_season(db, season_id, user)
    reveal = get_or_create_reveal(db, season)

    if request.query_params.get("share"):
        log_event_safe(db, "reveal_shared", uid=user.id, season_id=season.id)

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
    """«Следующий сезон» (§7.8) — ведёт обратно в онбординг (выбор следующего
    уровня той же цели или новой — делает человек сам)."""
    season = _own_season(db, season_id, user)
    log_event_safe(db, "next_season_started", uid=user.id, season_id=season.id)
    return RedirectResponse("/onboarding", status_code=303)
