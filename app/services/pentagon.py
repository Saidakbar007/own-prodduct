"""
Геометрия пятиугольной диаграммы профиля героя (5 сфер). Считаем координаты
в Python, а не в Jinja — у шаблонов нет встроенных sin/cos.

viewBox шире самого пятиугольника — под подписи нужен запас со всех сторон,
иначе длинные названия сфер ("Дисциплина", "Интеллект") обрезаются на краю.
Сам пятиугольник (MAX_RADIUS) не меняется, только поля вокруг него.
"""

import math

from app.services.spheres import MAX_LEVEL

MAX_RADIUS = 90

SIDE_MARGIN = 90  # запас по бокам под подписи (минимум по спецификации — 70)
TOP_MARGIN = 55  # запас сверху/снизу (минимум по спецификации — 40)
BOTTOM_MARGIN = 55
LABEL_OFFSET = 16  # отступ подписи от вершины пятиугольника (14-18px)

CENTER_X = MAX_RADIUS + SIDE_MARGIN
CENTER_Y = MAX_RADIUS + TOP_MARGIN
WIDTH = CENTER_X * 2
HEIGHT = CENTER_Y + MAX_RADIUS + BOTTOM_MARGIN

# Если |cos(угол)| меньше этого порога — вершина сверху/снизу (подпись по центру),
# иначе справа (подпись от начала) или слева (подпись до конца) от центра.
_HORIZONTAL_THRESHOLD = 0.15


def _angle(index: int) -> float:
    return math.radians(-90 + index * 72)


def _point(index: int, radius: float) -> tuple[float, float]:
    angle = _angle(index)
    return (CENTER_X + radius * math.cos(angle), CENTER_Y + radius * math.sin(angle))


def _anchor_for(index: int) -> str:
    cos_a = math.cos(_angle(index))
    if cos_a > _HORIZONTAL_THRESHOLD:
        return "start"  # справа от центра — подпись растёт вправо
    if cos_a < -_HORIZONTAL_THRESHOLD:
        return "end"  # слева от центра — подпись растёт влево
    return "middle"  # сверху/снизу — по центру вершины


def pentagon_chart(progress: list[dict]) -> dict:
    """
    progress: список из 5 {"code", "name", "xp", "level"} (порядок = оси
    по кругу). Возвращает всё готовое для SVG: точки данных, точки сетки
    (уровни 5/10/15/20) и позиции подписей с выравниванием по стороне.
    """
    data_points = []
    labels = []
    for i, sphere in enumerate(progress):
        fraction = sphere["level"] / MAX_LEVEL
        x, y = _point(i, MAX_RADIUS * fraction)
        data_points.append((x, y))

        # подпись всегда у внешнего кольца (не у точки данных) — иначе её
        # позиция прыгала бы при каждом изменении уровня
        lx, ly = _point(i, MAX_RADIUS + LABEL_OFFSET)
        labels.append(
            {
                "x": lx,
                "y": ly,
                "name": sphere["name"],
                "level": sphere["level"],
                "code": sphere["code"],
                "anchor": _anchor_for(i),
            }
        )

    grid_rings = []
    for ring_level in (5, 10, 15, 20):
        ring_fraction = ring_level / MAX_LEVEL
        ring_points = [_point(i, MAX_RADIUS * ring_fraction) for i in range(len(progress))]
        grid_rings.append(" ".join(f"{x:.1f},{y:.1f}" for x, y in ring_points))

    axis_lines = [_point(i, MAX_RADIUS) for i in range(len(progress))]

    return {
        "width": WIDTH,
        "height": HEIGHT,
        "center_x": CENTER_X,
        "center_y": CENTER_Y,
        "data_polygon": " ".join(f"{x:.1f},{y:.1f}" for x, y in data_points),
        "grid_rings": grid_rings,
        "axis_lines": axis_lines,
        "labels": labels,
        "all_level_one": all(sphere["level"] <= 1 for sphere in progress),
    }
