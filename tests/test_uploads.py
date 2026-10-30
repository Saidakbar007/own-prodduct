"""Автопроверки фото-доказательств (§9) — app/services/uploads.py."""

import random

import pytest
from PIL import Image, ImageFilter

from app.services import uploads


def _solid_image(color=(10, 10, 10), size=(200, 200)) -> Image.Image:
    return Image.new("RGB", size, color)


def _checkerboard_image(size=(200, 200), cell=10) -> Image.Image:
    img = Image.new("RGB", size)
    pixels = img.load()
    for x in range(size[0]):
        for y in range(size[1]):
            on = ((x // cell) + (y // cell)) % 2 == 0
            pixels[x, y] = (255, 255, 255) if on else (0, 0, 0)
    return img


def _noisy_image(size=(200, 200), seed=0) -> Image.Image:
    rnd = random.Random(seed)
    img = Image.new("RGB", size)
    pixels = img.load()
    for x in range(size[0]):
        for y in range(size[1]):
            v = rnd.randint(0, 255)
            pixels[x, y] = (v, v, v)
    return img


def _photo_like_image(size=(200, 200)) -> Image.Image:
    """Имитирует настоящее фото: ровный фон + один чёткий круг — в отличие
    от шахматки, устойчив к лёгкому блюру для aHash, но даёт понятный
    сигнал резкости на границе круга (ровный фон не создаёт ложных "краёв")."""
    img = Image.new("L", size, 60)
    pixels = img.load()
    cx, cy, r = size[0] // 2, size[1] // 2, size[0] // 4
    for x in range(size[0]):
        for y in range(size[1]):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                pixels[x, y] = 220
    return img.convert("RGB")


def test_is_blank_true_for_solid_color():
    assert uploads.is_blank(_solid_image()) is True


def test_is_blank_false_for_checkerboard():
    assert uploads.is_blank(_checkerboard_image()) is False


def test_is_blurry_true_for_blank_image():
    # ровная заливка -> нет никаких границ -> формально "размыто"
    assert uploads.is_blurry(_solid_image()) is True


def test_is_blurry_false_for_sharp_checkerboard():
    assert uploads.is_blurry(_checkerboard_image()) is False


def test_is_blurry_true_after_heavy_gaussian_blur():
    sharp = _photo_like_image()
    blurred = sharp.filter(ImageFilter.GaussianBlur(radius=12))
    assert uploads.is_blurry(sharp) is False
    assert uploads.is_blurry(blurred) is True


def test_average_hash_is_stable_for_same_image():
    img = _checkerboard_image()
    assert uploads.average_hash(img) == uploads.average_hash(img.copy())


def test_is_near_duplicate_true_for_identical_and_slightly_recompressed():
    img = _photo_like_image()
    h1 = uploads.average_hash(img)
    # лёгкое изменение (небольшой блюр, как при пересохранении) — то же фото
    h2 = uploads.average_hash(img.filter(ImageFilter.GaussianBlur(radius=1)))
    assert uploads.is_near_duplicate(h1, h2) is True


def test_is_near_duplicate_false_for_different_images():
    h1 = uploads.average_hash(_photo_like_image())
    h2 = uploads.average_hash(_noisy_image(seed=1))
    assert uploads.is_near_duplicate(h1, h2) is False


def test_save_photo_bytes_uses_unpredictable_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    name1 = uploads.save_photo_bytes(b"fake-bytes-1", "photo.jpg")
    name2 = uploads.save_photo_bytes(b"fake-bytes-2", "photo.jpg")
    assert name1 != name2
    assert not name1.split(".")[0].isdigit()  # не последовательный id/таймстамп
    assert (tmp_path / "uploads" / name1).exists()


def test_save_photo_bytes_falls_back_to_jpg_for_unknown_extension(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    name = uploads.save_photo_bytes(b"data", "weird.exe")
    assert name.endswith(".jpg")


def test_analyze_photo_reports_all_signals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    img = _checkerboard_image()
    path = tmp_path / "test.png"
    img.save(path)
    result = uploads.analyze_photo(str(path))
    assert set(result.keys()) == {"phash", "is_blank", "is_blurry"}
    assert result["is_blank"] is False
    assert result["is_blurry"] is False
