"""
Геометрия пятиугольной диаграммы профиля героя (5 сфер). Считаем координаты
в Python, а не в Jinja — у шаблонов нет встроенных sin/cos.
"""

import math

from app.services.spheres import MAX_LEVEL

SIZE = 220
CENTER = SIZE / 2
MAX_RADIUS = 90


def _point(index: int, fraction: float) -> tuple[float, float]:
    angle = math.radians(-90 + index * 72)
    radius = MAX_RADIUS * fraction
    return (CENTER + radius * math.cos(angle), CENTER + radius * math.sin(angle))


def pentagon_chart(progress: list[dict]) -> dict:
    """
    progress: список из 5 {"code", "name", "xp", "level"} (порядок = оси
    по кругу). Возвращает всё готовое для SVG: точки данных, точки сетки
    (уровни 5/10/15/20) и позиции подписей.
    """
    data_points = []
    labels = []
    for i, sphere in enumerate(progress):
        fraction = sphere["level"] / MAX_LEVEL
        x, y = _point(i, fraction)
        data_points.append((x, y))

        lx, ly = _point(i, 1.22)
        labels.append({"x": lx, "y": ly, "name": sphere["name"], "level": sphere["level"], "code": sphere["code"]})

    grid_rings = []
    for ring_level in (5, 10, 15, 20):
        ring_fraction = ring_level / MAX_LEVEL
        ring_points = [_point(i, ring_fraction) for i in range(len(progress))]
        grid_rings.append(" ".join(f"{x:.1f},{y:.1f}" for x, y in ring_points))

    axis_lines = [_point(i, 1.0) for i in range(len(progress))]

    return {
        "size": SIZE,
        "center": CENTER,
        "data_polygon": " ".join(f"{x:.1f},{y:.1f}" for x, y in data_points),
        "grid_rings": grid_rings,
        "axis_lines": axis_lines,
        "labels": labels,
    }
