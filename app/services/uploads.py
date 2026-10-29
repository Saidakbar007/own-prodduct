"""
Фото-доказательства (§9): сохранение под непредсказуемым именем + простые
автопроверки без сети и без ИИ — перцептивный хэш (поиск повторов в сезоне),
пустые/чёрные снимки, размытость. Чистые функции над PIL.Image, что можно
покрыть юнит-тестами на сгенерированных картинках (tests/test_uploads.py).
"""

import os
import secrets

from PIL import Image, ImageFilter

UPLOADS_DIR = "uploads"
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
DUPLICATE_HAMMING_THRESHOLD = 5
BLUR_VARIANCE_THRESHOLD = 180.0
BLANK_STD_THRESHOLD = 4.0


def save_photo_bytes(data: bytes, original_filename: str) -> str:
    """Сохраняет байты файла в uploads/ под непредсказуемым именем (§9:
    "хранить с непредсказуемыми именами файлов"). Возвращает имя файла."""
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    ext = os.path.splitext(original_filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"
    filename = f"{secrets.token_hex(16)}{ext}"
    with open(os.path.join(UPLOADS_DIR, filename), "wb") as out:
        out.write(data)
    return filename


def average_hash(image: Image.Image, hash_size: int = 8) -> str:
    """aHash без внешних зависимостей: уменьшаем до hash_size×hash_size в
    оттенках серого, сравниваем каждый пиксель со средней яркостью."""
    small = image.convert("L").resize((hash_size, hash_size), Image.LANCZOS)
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p >= avg else "0" for p in pixels)
    return f"{int(bits, 2):0{len(bits) // 4}x}"


def hamming_distance(hash_a: str, hash_b: str) -> int:
    return bin(int(hash_a, 16) ^ int(hash_b, 16)).count("1")


def is_near_duplicate(hash_a: str, hash_b: str, threshold: int = DUPLICATE_HAMMING_THRESHOLD) -> bool:
    """Правда ли, что два фото почти совпадают — перепосланное старое фото (§9)."""
    return hamming_distance(hash_a, hash_b) <= threshold


def _grayscale_pixels(image: Image.Image, size: int) -> list[int]:
    return list(image.convert("L").resize((size, size)).getdata())


def _mean_variance(pixels: list[int]) -> tuple[float, float]:
    mean = sum(pixels) / len(pixels)
    variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)
    return mean, variance


def is_blank(image: Image.Image, std_threshold: float = BLANK_STD_THRESHOLD) -> bool:
    """Пустой/чёрный/засвеченный кадр — почти нулевой разброс яркости."""
    pixels = _grayscale_pixels(image, 64)
    _, variance = _mean_variance(pixels)
    return variance**0.5 < std_threshold


def is_blurry(image: Image.Image, variance_threshold: float = BLUR_VARIANCE_THRESHOLD) -> bool:
    """Оценка размытости: дисперсия яркости на карте границ (FIND_EDGES).
    Резкое фото даёт высокую дисперсию (чёткие края), размытое — низкую."""
    edges = image.convert("L").resize((200, 200)).filter(ImageFilter.FIND_EDGES)
    _, variance = _mean_variance(list(edges.getdata()))
    return variance < variance_threshold


def analyze_photo(path: str) -> dict:
    """Запускает все автопроверки над сохранённым файлом разом."""
    with Image.open(path) as img:
        img.load()
        return {
            "phash": average_hash(img),
            "is_blank": is_blank(img),
            "is_blurry": is_blurry(img),
        }
