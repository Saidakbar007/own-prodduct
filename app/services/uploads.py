"""
Сохранение загруженных фото-доказательств. Время и имя файла ставит сервер.
"""

import os
import uuid
from datetime import datetime, timezone

from fastapi import UploadFile

UPLOADS_DIR = "uploads"


def save_proof_photo(file: UploadFile) -> str:
    """
    Сохраняет загруженный файл в uploads/ под уникальным именем.
    Возвращает относительный путь (для ссылки через /uploads/...).
    """
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        ext = ".jpg"

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{uuid.uuid4().hex[:8]}{ext}"
    path = os.path.join(UPLOADS_DIR, filename)

    with open(path, "wb") as out:
        out.write(file.file.read())

    return f"{UPLOADS_DIR}/{filename}"
