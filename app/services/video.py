"""
Reveal-видео (§10 ТЗ): короткий MP4 (≤20 сек) из фото-доказательств и цифр.
ffmpeg — через imageio-ffmpeg (бинарник уже в пакете, скачивать не нужно);
если недоступен — коллаж-PNG (app/services/cards.py использует тот же стиль).

Генерация синхронная (без очереди задач) — кадров мало (≤6), укладывается
в несколько секунд; ограничение длины и кэширование — см. app/routers/reveal.py.
"""

import os
import subprocess
from typing import Optional

from PIL import Image

MAX_SECONDS = 20
MAX_FRAMES = 6


def ffmpeg_available() -> bool:
    try:
        import imageio_ffmpeg

        return os.path.exists(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return False


def render_reveal_video(frame_paths: list[str], output_path: str) -> Optional[str]:
    """Слайд-шоу MP4 1080×1920 из кадров. None, если ffmpeg недоступен или
    генерация не удалась — тогда использовать render_collage как фолбэк."""
    frames = [p for p in frame_paths if os.path.exists(p)][:MAX_FRAMES]
    if not frames:
        return None
    try:
        import imageio_ffmpeg

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

    per_frame = max(1.0, MAX_SECONDS / len(frames))
    list_file = output_path + ".txt"
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for p in frames:
                f.write(f"file '{os.path.abspath(p)}'\n")
                f.write(f"duration {per_frame}\n")
            f.write(f"file '{os.path.abspath(frames[-1])}'\n")

        cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x15120f",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "24",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    except Exception:
        return None
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)

    return output_path if os.path.exists(output_path) else None


def render_collage(frame_paths: list[str], output_path: str, cols: int = 2) -> str:
    """Фолбэк без ffmpeg: статичный коллаж-PNG из кадров."""
    frames = [p for p in frame_paths if os.path.exists(p)][:MAX_FRAMES] or []
    images = [Image.open(p).convert("RGB") for p in frames]
    if not images:
        images = [Image.new("RGB", (1080, 1920), (21, 18, 15))]

    rows = max(1, (len(images) + cols - 1) // cols)
    thumb_w = 1080 // cols
    thumb_h = 1920 // rows
    canvas = Image.new("RGB", (thumb_w * cols, thumb_h * rows), (21, 18, 15))
    for i, img in enumerate(images):
        img = img.resize((thumb_w, thumb_h))
        x = (i % cols) * thumb_w
        y = (i // cols) * thumb_h
        canvas.paste(img, (x, y))
    canvas.save(output_path, format="PNG")
    return output_path
