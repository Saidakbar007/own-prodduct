"""
Отдаёт фото-доказательства — только владельцу (§9: "все фото по умолчанию
видны только владельцу"). Никакого публичного /uploads-маунта: путь к файлу
непредсказуем, но доступ всё равно проверяется по uid.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.auth import require_user
from app.database import get_session
from app.models import Proof, User

router = APIRouter()


@router.get("/proofs/{proof_id}")
def get_proof(proof_id: int, user: User = Depends(require_user), db: Session = Depends(get_session)):
    proof = db.get(Proof, proof_id)
    if not proof or proof.uid != user.id:
        raise HTTPException(status_code=404)
    path = os.path.join("uploads", proof.filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type=proof.content_type)
