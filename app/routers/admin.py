"""
Админка (v6d): только для логинов из ADMIN_LOGINS (require_admin — 404
для всех остальных). /admin — общая точка входа со ссылками на галерею
ассетов и песочницу своего аккаунта.
"""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.auth import require_admin
from app.database import get_session
from app.models import User
from app.rendering import render
from app.services.gallery import build_gallery

router = APIRouter()


@router.get("/admin")
def admin_home(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    return render(request, "admin/index.html", {"user": user}, db=db, user=user)


@router.get("/admin/gallery")
def admin_gallery(request: Request, user: User = Depends(require_admin), db: Session = Depends(get_session)):
    gallery = build_gallery(db)
    return render(request, "admin/gallery.html", {"user": user, "gallery": gallery}, db=db, user=user)
