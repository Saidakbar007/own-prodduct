"""
Нарезка спрайт-листов (5 фигур в ряд, 1536x1024) на отдельные WebP-кадры.

- Убирает белый фон (если нет альфы) с плавным краем, без белых ореолов
  (difference matting от белого + "размикс" цвета, чтобы снять белую примесь
  с полупрозрачных пикселей свечения).
- Находит границы между фигурами по профилю "детализации" (градиент
  яркости) по столбцам — гладкий фон/свечение даёт низкую детализацию,
  силуэт персонажа — высокую. Работает даже когда свечение соседних фигур
  визуально соприкасается (как у героя на поздних стадиях).
- Один общий масштаб на весь лист (стадии не выравниваются по росту),
  низ фигур на одной линии, одинаковый прозрачный холст с запасом по краям.

Разовый инструмент для подготовки арта — не часть приложения в рантайме,
поэтому Pillow/numpy/scipy не добавлены в requirements.txt. Для запуска:
    pip install pillow numpy scipy
    python scripts/process_art.py  # берёт art_sources/, пишет в app/static/game/
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

CANVAS = 480
MARGIN = 22
BBOX_ALPHA_THRESHOLD = 5
BBOX_PAD = 18
N_FIGURES = 5


SOLID_THRESHOLD = 195  # min(R,G,B) ниже этого — считаем пиксель полностью непрозрачным


def remove_white_background(rgb: np.ndarray) -> np.ndarray:
    """
    Difference matting от белого с порогом: пиксели, заметно отличающиеся
    от белого (min(R,G,B) <= SOLID_THRESHOLD), остаются полностью
    непрозрачными (не тускнеют) — плавный край появляется только в узкой
    зоне перехода к чистому фону. Затем "размикс" цвета в этой зоне убирает
    белую примесь (иначе на тёмном фоне виден белый ореол вокруг свечения).
    """
    rgb_f = rgb.astype(np.float32)
    min_channel = rgb_f.min(axis=2)

    span = 255.0 - SOLID_THRESHOLD
    alpha = np.clip((255.0 - min_channel) / span * 255.0, 0.0, 255.0)
    alpha = np.where(min_channel <= SOLID_THRESHOLD, 255.0, alpha)
    # Фон редко бывает чистым (255,255,255) — обычно ~253-254 из-за сжатия,
    # что даёт едва заметную, но сплошную полупрозрачность по всему полю.
    # Срезаем этот шумовой пол, оставляя только настоящий плавный край.
    alpha = np.where(alpha < 16.0, 0.0, alpha)

    a_norm = (alpha / 255.0)[:, :, None]
    fg = (rgb_f - (1 - a_norm) * 255.0) / np.clip(a_norm, 0.02, 1.0)
    fg = np.clip(fg, 0, 255)

    # Для почти полностью прозрачных пикселей размикс нестабилен — но раз
    # alpha ~ 0, их цвет всё равно не виден, оставляем исходный цвет.
    low_alpha_mask = (alpha < 8)[:, :, None]
    fg = np.where(low_alpha_mask, rgb_f, fg)

    out = np.dstack([fg, alpha[:, :, None]]).astype(np.uint8)
    return out


def detail_profile(gray: np.ndarray) -> np.ndarray:
    """Профиль детализации по столбцам — градиент яркости (не зависит от яркости фона)."""
    gx = np.abs(np.diff(gray.astype(np.float32), axis=1, prepend=gray[:, :1].astype(np.float32)))
    gy = np.abs(np.diff(gray.astype(np.float32), axis=0, prepend=gray[:1, :].astype(np.float32)))
    edge = gx + gy
    return edge.sum(axis=0)  # сумма по столбцу


def find_splits(profile: np.ndarray, width: int, n: int = N_FIGURES, window_frac: float = 0.22) -> list[int]:
    """4 границы между n фигурами — минимум профиля в окне вокруг равномерных точек деления."""
    splits = []
    for i in range(1, n):
        expected = int(width * i / n)
        half_window = int(width / n * window_frac * 2)
        lo = max(0, expected - half_window)
        hi = min(width, expected + half_window)
        segment = profile[lo:hi]
        split = lo + int(np.argmin(segment))
        splits.append(split)
    return splits


def tight_bbox(alpha: np.ndarray, threshold: int = BBOX_ALPHA_THRESHOLD, pad: int = BBOX_PAD):
    mask = alpha > threshold
    if not mask.any():
        return None
    ys, xs = np.where(mask)
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    y0 = max(0, y0 - pad)
    x0 = max(0, x0 - pad)
    y1 = min(alpha.shape[0] - 1, y1 + pad)
    x1 = min(alpha.shape[1] - 1, x1 + pad)
    return x0, y0, x1, y1


def process_sheet(path: Path, already_alpha: bool) -> list[Image.Image]:
    im = Image.open(path).convert("RGBA")
    arr = np.array(im)
    rgb = arr[:, :, :3]
    gray = np.array(Image.fromarray(rgb).convert("L"))

    if already_alpha:
        rgba = arr
    else:
        rgba = remove_white_background(rgb)

    profile = detail_profile(gray)
    width = im.size[0]
    splits = find_splits(profile, width)
    bounds = [0] + splits + [width]

    crops = []
    boxes = []
    for i in range(N_FIGURES):
        x0, x1 = bounds[i], bounds[i + 1]
        region = rgba[:, x0:x1, :]
        bbox = tight_bbox(region[:, :, 3])
        if bbox is None:
            bbox = (0, 0, region.shape[1] - 1, region.shape[0] - 1)
        bx0, by0, bx1, by1 = bbox
        crop = region[by0 : by1 + 1, bx0 : bx1 + 1, :]
        crops.append(crop)
        boxes.append((bx1 - bx0 + 1, by1 - by0 + 1))

    avail = CANVAS - 2 * MARGIN
    scale = min(avail / w for w, h in boxes) if boxes else 1.0
    scale = min(scale, min(avail / h for w, h in boxes))

    outputs = []
    for crop in crops:
        h, w = crop.shape[0], crop.shape[1]
        new_w = max(1, round(w * scale))
        new_h = max(1, round(h * scale))
        fig_im = Image.fromarray(crop, mode="RGBA").resize((new_w, new_h), Image.LANCZOS)

        canvas = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
        paste_x = (CANVAS - new_w) // 2
        paste_y = CANVAS - MARGIN - new_h  # низ на одной линии
        canvas.alpha_composite(fig_im, (paste_x, paste_y))
        outputs.append(canvas)

    return outputs


# Исходники в art_sources/ -> (уже с альфой?, префикс файла, папка в static/game/)
SHEETS = [
    ("Эволюция героя_ от странника к паладину.png", True, "hero", "hero"),
    ("Эволюция духа-воина (1).png", False, "warrior", "persona"),
    ("Эволюция мага_ от ученика к легенде.png", False, "sage", "persona"),
    ("Эволюция монаха времени.png", False, "monk", "persona"),
    ("Прогрессия лесного целителя-мага.png", False, "healer", "persona"),
    ("Эволюция легендарного барда.png", False, "bard", "persona"),
]


def run_all(sources_dir: Path, static_game_dir: Path) -> list[Path]:
    written = []
    for filename, already_alpha, prefix, subdir in SHEETS:
        src = sources_dir / filename
        out_dir = static_game_dir / subdir
        out_dir.mkdir(parents=True, exist_ok=True)

        frames = process_sheet(src, already_alpha)
        for i, frame in enumerate(frames, start=1):
            out_path = out_dir / f"{prefix}_{i}.webp"
            frame.save(out_path, "WEBP", quality=85)
            written.append(out_path)
    return written


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    sources_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else project_root / "art_sources"
    static_game_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else project_root / "app" / "static" / "game"

    for out_path in run_all(sources_dir, static_game_dir):
        print(out_path)
