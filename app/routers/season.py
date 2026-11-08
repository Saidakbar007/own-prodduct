"""
«Сезоны»: хаб (текущие сезоны, каталог шаблонов, полка завершённых) и
детальная страница одного сезона — «откуда → куда», день N из M, прогноз
простыми словами, компактный календарь, «Проверка результата» (бывший
«Замер», §7.3/§7.4 ТЗ, переименовано UX-правкой).
"""

import math
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth import require_user
from app.database import get_session
from app.i18n import translate
from app.models import Measurement, Season, SeasonDay, SphereState, User
from app.rendering import render
from app.newlife.conversation_starters_bank import conversation_starters_for_display
from app.newlife.goal_catalog import goal_meta, guide_for_display, ladder_for_display
from app.newlife.resources_bank import resources_for_goal
from app.newlife.spheres import SPHERES, is_valid_sphere
from app.services.events import log_event_safe
from app.services.flash import push_flash
from app.seasons_library.catalog_meta import poster_hero_for
from app.seasons_library.loader import get_template, load_library

# Кольцо прогресса сезона — тот же радиус/длина окружности, что на "Сегодня"
# (app/routers/today.py::RING_RADIUS), чтобы кольца визуально совпадали.
RING_RADIUS = 36
RING_CIRCUMFERENCE = 2 * math.pi * RING_RADIUS

_SPHERE_ICONS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "icons" / "spheres"


@lru_cache(maxsize=None)
def _sphere_icon_svg(sphere_id: str) -> str:
    """Инлайн-разметка неоновой иконки сферы (assets/icons/spheres/<id>.svg) —
    инлайним, а не <img src>, потому что иконки рисуются stroke="currentColor"
    и свечение (.sphere-glow/.sphere-dim, design/components.css) работает
    только для инлайн-SVG внутри страницы."""
    path = _SPHERE_ICONS_DIR / f"{sphere_id}.svg"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""

_DEFAULT_CATALOG_META = {
    "difficulty": "Свой уровень",
    "for_whom": "Под твою собственную цель",
    "outcome": "Результат — по условиям, которые задаёт сама цель",
}


def _display_meta(template_id: str) -> dict:
    """Текст карточки каталога (§7 PRD «Откуда эти нормы»): из
    content/spheres/*.yaml, с запасным текстом для шаблонов без каталога
    (своя цель от ИИ — см. BACKLOG.md)."""
    entry = goal_meta(template_id)
    if entry is None:
        return _DEFAULT_CATALOG_META
    return {"difficulty": entry.difficulty, "for_whom": entry.for_whom, "outcome": entry.outcome}
from app.services.seasons import (
    MAX_ACTIVE_SEASONS,
    compute_forecast,
    ensure_days_built_for_today,
    get_active_seasons,
    get_current_season,
    sync_season_state,
)
from app.services.usertime import today_for

router = APIRouter()


def _template_sphere(template_id: str) -> Optional[str]:
    """К какой из 11 сфер относится шаблон сезона — через goal_meta (NEWLIFE_2_0.md
    §3.2: "Цели" = сетка сфер → сезоны внутри сферы). None для шаблонов без
    записи в content/spheres/*.yaml (ИИ-черновик — см. BACKLOG.md), такой
    сезон не попадёт ни на одну сферную страницу (ограничение контента, не
    этого роутера)."""
    entry = goal_meta(template_id)
    return entry.sphere if entry else None


@router.get("/seasons")
def seasons_hub(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Сетка 11 сфер (NEWLIFE_2_0.md §3.2, Задача 1): выбранные пользователем
    сферы — ярко (.sphere-glow), остальные — приглушённо (.sphere-dim) с
    кнопкой "Добавить" на существующий флоу выбора сфер в онбординге. Клик по
    активной сфере ведёт на /seasons/{sphere_id} (список сезонов сферы)."""
    states = {
        s.sphere_id: s
        for s in db.exec(select(SphereState).where(SphereState.uid == user.id)).all()
    }
    tiles = [
        {
            "sphere": sphere,
            "icon_svg": _sphere_icon_svg(sphere.id),
            "active": bool(states.get(sphere.id) and states[sphere.id].active),
        }
        for sphere in SPHERES
    ]

    return render(
        request,
        "seasons_hub.html",
        {
            "tiles": tiles,
            "lang": user.language,
        },
    )


@router.get("/seasons/{sphere_id}")
def seasons_sphere(
    sphere_id: str, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)
):
    """Сезоны и каталог одной сферы (NEWLIFE_2_0.md §3.2, Задача 2): активные
    сезоны пользователя в этой сфере с живым кольцом прогресса, затем шаблоны
    этой сферы, которых пользователь ещё не начинал."""
    if not is_valid_sphere(sphere_id):
        raise HTTPException(status_code=404)
    sphere = next(s for s in SPHERES if s.id == sphere_id)

    today = today_for(user)
    active = get_active_seasons(db, user.id)
    for season in active:
        ensure_days_built_for_today(db, season, today)
        sync_season_state(db, season, today)
    # sync_season_state может перевести сезон в "finished" — перечитываем список.
    active = get_active_seasons(db, user.id)
    active_in_sphere = [s for s in active if _template_sphere(s.template_id) == sphere_id]

    active_cards = []
    for s in active_in_sphere:
        day_number = max(1, (today - s.start_date).days + 1)
        percent = min(1.0, day_number / s.length_days) if s.length_days else 0.0
        active_cards.append(
            {
                "season": s,
                "day_number": day_number,
                "ring_circumference": round(RING_CIRCUMFERENCE, 1),
                "ring_offset": round(RING_CIRCUMFERENCE * (1 - percent), 1),
            }
        )

    started_template_ids = {
        s.template_id for s in db.exec(select(Season).where(Season.uid == user.id)).all()
    }
    catalog = [
        {
            "template": t,
            "meta": _display_meta(t.id),
        }
        for t in sorted(load_library().values(), key=lambda t: t.id)
        if _template_sphere(t.id) == sphere_id and t.id not in started_template_ids
    ]

    return render(
        request,
        "seasons_hub.html",
        {
            "sphere": sphere,
            "icon_svg": _sphere_icon_svg(sphere.id),
            "active_cards": active_cards,
            "catalog": catalog,
            "can_start": len(active) < MAX_ACTIVE_SEASONS,
            "lang": user.language,
        },
    )


@router.get("/season")
def season_redirect(request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)):
    """Удобная ссылка без id — на текущий выбранный сезон."""
    season = get_current_season(db, user.id, request)
    if season:
        return RedirectResponse(f"/season/{season.id}", status_code=303)
    return RedirectResponse("/seasons", status_code=303)


def _own_season(db: Session, season_id: int, user: User) -> Season:
    season = db.get(Season, season_id)
    if not season or season.uid != user.id:
        raise HTTPException(status_code=404)
    return season


@router.post("/season/{season_id}/ladder/advance")
def ladder_advance(
    season_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)
):
    """Отметить текущую ступень лестницы сделанной — переход только по
    порядку (§F: нельзя перескочить), следующий визит показывает следующий
    вызов. Без штрафа и без привязки к дню сезона — ступени добровольны."""
    season = _own_season(db, season_id, user)
    rungs = ladder_for_display(season.template_id, user.language)
    if rungs and season.ladder_rung < len(rungs):
        season.ladder_rung += 1
        db.add(season)
        db.commit()
        log_event_safe(db, "ladder_rung_done", uid=user.id, season_id=season.id)
    return RedirectResponse(f"/season/{season_id}", status_code=303)


@router.post("/season/{season_id}/ladder/skip")
def ladder_skip(
    season_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)
):
    """«Не сегодня» — без штрафа, ступень остаётся текущей (guide целей
    явно обещает: пропуск не наказывается)."""
    season = _own_season(db, season_id, user)
    log_event_safe(db, "ladder_rung_skipped", uid=user.id, season_id=season.id)
    push_flash(request, "season.ladder_skip_flash", "info")
    return RedirectResponse(f"/season/{season_id}", status_code=303)


@router.get("/season/{season_id}")
def season_detail(
    season_id: int, request: Request, user: User = Depends(require_user), db: Session = Depends(get_session)
):
    season = _own_season(db, season_id, user)

    today = today_for(user)
    if season.status == "active":
        ensure_days_built_for_today(db, season, today)
        season = sync_season_state(db, season, today)

    if season.status == "finished":
        return RedirectResponse(f"/season/{season.id}/reveal", status_code=303)

    days = db.exec(
        select(SeasonDay).where(SeasonDay.season_id == season.id).order_by(SeasonDay.day_number)
    ).all()
    measurements = db.exec(
        select(Measurement).where(Measurement.season_id == season.id).order_by(Measurement.day_number)
    ).all()

    today_number = max(1, (today - season.start_date).days + 1)
    sparkline = _build_sparkline(measurements)
    forecast = compute_forecast(db, season, today_number)

    present_statuses = sorted({d.status for d in days if d.status != "planned"})
    if any(d.status == "planned" and d.calendar_date >= today for d in days):
        present_statuses.append("future")

    return render(
        request,
        "season_detail.html",
        {
            "season": season,
            "days": days,
            "measurements": measurements,
            "today_number": today_number,
            "sparkline": sparkline,
            "forecast": round(forecast, 1),
            "present_statuses": present_statuses,
            "poster_hero": poster_hero_for(season.template_id),
            "guide": guide_for_display(season.template_id, user.language),
            "ladder": _ladder_context(season, user.language),
            "conversation_starters": (
                conversation_starters_for_display(user.language)
                if season.template_id == "start_conversations"
                else None
            ),
            "resources": resources_for_goal(season.template_id, user.language),
            "roadmap": _build_roadmap(season, today_number, user.language),
            "lang": user.language,
        },
    )


# Роудмап-«тропа» (NEWLIFE_2_0.md §3.2, Задача 3) — только для сфер, где уже
# есть богатая прогрессия YAML-шаблона (Тело/Разум/Энергия); остальные 8 сфер
# оставлены без изменений в season_detail.html осознанно (экономия времени
# дедлайна, см. отчёт в V2_PROGRESS.md/BACKLOG.md).
_ROADMAP_SPHERES = {"body", "mind", "energy"}


def _build_roadmap(season: Season, today_number: int, lang: str) -> Optional[dict]:
    sphere_id = _template_sphere(season.template_id)
    if sphere_id not in _ROADMAP_SPHERES:
        return None
    try:
        template = get_template(season.template_id)
    except KeyError:
        return None

    phases = template.phases
    total_phases = len(phases)
    current_phase = min(max(season.current_phase, 1), total_phases)
    length_days = season.length_days or 1

    if total_phases > 1:
        # Богатая прогрессия (например run_5k — 5 фаз от baseline): один шаг
        # роудмапа = одна фаза шаблона, "Ты здесь" = season.current_phase.
        # Диапазон дней — равные доли length_days (в YAML нет явных дней на
        # фазу, только пороги baseline), это приближение для визуала тропы.
        steps = []
        for p in template.phases:
            start_day = round((p.phase - 1) / total_phases * length_days) + 1
            end_day = round(p.phase / total_phases * length_days)
            if p.phase < current_phase:
                status = "done"
            elif p.phase == current_phase:
                status = "here"
            else:
                status = "future"
            steps.append(
                {
                    "title": p.days[0].title,
                    "days_label": translate(lang, "season.roadmap_days_label", start=start_day, end=max(end_day, start_day)),
                    "unlock_label": translate(
                        lang, "season.roadmap_unlock_label", value=p.unlock_if_baseline_gte, unit=template.metric.unit
                    ),
                    "status": status,
                }
            )
        current_number = current_phase
    else:
        # Шаблон с одной фазой (сейчас — все текущие Mind/Energy сезоны):
        # нет пороговой прогрессии в YAML, поэтому тропа — по неделям сезона
        # (length_days/7), "Ты здесь" = текущая неделя по дню сезона.
        weeks = max(1, math.ceil(length_days / 7))
        current_week = min(max(math.ceil(today_number / 7), 1), weeks)
        steps = []
        for w in range(1, weeks + 1):
            start_day = (w - 1) * 7 + 1
            end_day = min(w * 7, length_days)
            if w < current_week:
                status = "done"
            elif w == current_week:
                status = "here"
            else:
                status = "future"
            steps.append(
                {
                    "title": translate(lang, "season.roadmap_week_label", n=w),
                    "days_label": translate(lang, "season.roadmap_days_label", start=start_day, end=end_day),
                    "unlock_label": None,
                    "status": status,
                }
            )
        total_phases = weeks
        current_number = current_week

    return {
        "sphere_id": sphere_id,
        "steps": steps,
        "current_number": current_number,
        "total": total_phases,
    }


def _ladder_context(season: Season, lang: str) -> Optional[dict]:
    rungs = ladder_for_display(season.template_id, lang)
    if not rungs:
        return None
    current = min(max(season.ladder_rung, 1), len(rungs))
    return {
        "rungs": rungs,
        "current_index": current - 1,
        "current_number": current,
        "total": len(rungs),
        "is_last": current >= len(rungs),
    }


def _build_sparkline(measurements, width: int = 280, height: int = 48) -> dict:
    """Готовые точки для SVG-полилинии замеров (без JS, считаем на сервере)."""
    values = [m.value for m in measurements]
    if len(values) < 2:
        return {"line": "", "area": "", "has_data": False}

    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = width / (len(values) - 1)

    points = [
        (round(i * step, 1), round(height - ((v - lo) / span) * height, 1))
        for i, v in enumerate(values)
    ]
    line = " ".join(f"{x} {y}" for x, y in points)
    area = f"0 {height} " + line + f" {width} {height}"
    return {
        "line": "M" + " L".join(f"{x} {y}" for x, y in points),
        "area": "M" + f"0 {height} L" + " L".join(f"{x} {y}" for x, y in points) + f" L{width} {height} Z",
        "last_x": points[-1][0],
        "last_y": points[-1][1],
        "has_data": True,
    }
