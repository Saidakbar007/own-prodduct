"""Reveal-видео (§10) — ffmpeg слайд-шоу и фолбэк-коллаж."""

import os

import pytest
from PIL import Image

from app.services import video


def _make_frame(path, color):
    Image.new("RGB", (400, 600), color).save(path)
    return path


def test_render_collage_without_frames_still_produces_file(tmp_path):
    out = str(tmp_path / "collage.png")
    result = video.render_collage([], out)
    assert result == out
    assert os.path.exists(out)
    img = Image.open(out)
    assert img.size[0] > 0 and img.size[1] > 0


def test_render_collage_with_frames(tmp_path):
    frame1 = _make_frame(str(tmp_path / "f1.png"), (255, 0, 0))
    frame2 = _make_frame(str(tmp_path / "f2.png"), (0, 255, 0))
    out = str(tmp_path / "collage.png")
    result = video.render_collage([frame1, frame2], out)
    assert os.path.exists(result)


def test_render_reveal_video_returns_none_for_no_frames(tmp_path):
    out = str(tmp_path / "out.mp4")
    assert video.render_reveal_video([], out) is None


@pytest.mark.skipif(not video.ffmpeg_available(), reason="ffmpeg binary not available in this environment")
def test_render_reveal_video_produces_mp4(tmp_path):
    frame1 = _make_frame(str(tmp_path / "f1.png"), (255, 0, 0))
    frame2 = _make_frame(str(tmp_path / "f2.png"), (0, 0, 255))
    out = str(tmp_path / "out.mp4")
    result = video.render_reveal_video([frame1, frame2], out)
    assert result == out
    assert os.path.exists(out)
    assert os.path.getsize(out) > 1000
