"""
E2e-тесты диаграммы героя: подписи не обрезаются и не наезжают на
заголовок карточки или друг на друга — на 375/768/1280px, в обеих темах.
Плюс общий скан других страниц на обрезанный/наезжающий текст.
"""

import pytest

VIEWPORTS = [375, 768, 1280]


def _assert_labels_fit(page, base_url: str, path: str):
    """
    Для каждой подписи на диаграмме: её bounding box целиком внутри
    карточки, не пересекается с заголовком "Профиль героя" и не
    пересекается с другими подписями.
    """
    page.goto(f"{base_url}{path}")
    page.wait_for_load_state("networkidle")

    title = page.locator("text=Профиль героя").first
    title_box = title.bounding_box()
    assert title_box is not None, f"нет заголовка 'Профиль героя' на {path}"

    card = title.locator("xpath=ancestor::*[contains(@class,'rounded-xl')][1]")
    card_box = card.bounding_box()
    assert card_box is not None, f"нет карточки-контейнера на {path}"

    svg = page.locator("svg[aria-label='Диаграмма сфер героя']").first
    assert svg.is_visible(), f"диаграмма не видна на {path}"

    labels = svg.locator("text[data-sphere]")
    count = labels.count()
    assert count == 5, f"ожидалось 5 подписей сфер, получено {count} на {path}"

    boxes = [labels.nth(i).bounding_box() for i in range(count)]

    def overlaps(a, b) -> bool:
        return not (
            a["x"] + a["width"] <= b["x"]
            or b["x"] + b["width"] <= a["x"]
            or a["y"] + a["height"] <= b["y"]
            or b["y"] + b["height"] <= a["y"]
        )

    for i, box in enumerate(boxes):
        assert box is not None, f"подпись {i} не отрисовалась на {path}"
        inside_card = (
            box["x"] >= card_box["x"] - 1
            and box["y"] >= card_box["y"] - 1
            and box["x"] + box["width"] <= card_box["x"] + card_box["width"] + 1
            and box["y"] + box["height"] <= card_box["y"] + card_box["height"] + 1
        )
        assert inside_card, (
            f"подпись {i} выходит за пределы карточки на {path} "
            f"(label={box}, card={card_box}) — обрезается на краю диаграммы"
        )
        assert not overlaps(box, title_box), (
            f"подпись {i} наезжает на заголовок 'Профиль героя' на {path} (label={box}, title={title_box})"
        )

    for i in range(count):
        for j in range(i + 1, count):
            assert not overlaps(boxes[i], boxes[j]), (
                f"подпись {i} наезжает на подпись {j} на {path} ({boxes[i]} vs {boxes[j]})"
            )


@pytest.mark.parametrize("width", VIEWPORTS)
@pytest.mark.parametrize("path", ["/", "/profile"])
def test_pentagon_labels_fit_without_clipping_or_overlap(demo_page, e2e_server, path, width):
    demo_page.set_viewport_size({"width": width, "height": 900})
    _assert_labels_fit(demo_page, e2e_server, path)


@pytest.mark.parametrize("width", VIEWPORTS)
def test_pentagon_labels_fit_in_dark_theme(demo_page, e2e_server, width):
    demo_page.set_viewport_size({"width": width, "height": 900})
    demo_page.goto(f"{e2e_server}/")
    demo_page.wait_for_load_state("networkidle")
    demo_page.evaluate("document.documentElement.classList.add('dark')")
    _assert_labels_fit(demo_page, e2e_server, "/")


def test_hint_shown_when_all_spheres_at_level_one(page, e2e_server):
    page.goto(f"{e2e_server}/register")
    page.fill('input[name="name"]', "Тест")
    page.fill('input[name="mail"]', "pentagon_fresh@example.com")
    page.fill('input[name="login"]', "pentagon_fresh")
    page.fill('input[name="password"]', "secret123")
    page.fill('input[name="password_confirm"]', "secret123")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")

    page.goto(f"{e2e_server}/")
    page.wait_for_load_state("networkidle")
    assert page.locator("text=Отмечай привычки — профиль начнёт расти").count() == 1


def test_no_clipped_or_overflowing_text_across_main_pages(demo_page, e2e_server):
    """
    Общий скан: ни на одной основной странице элемент не должен быть
    обрезан (scrollWidth > clientWidth) и страница не должна требовать
    горизонтального скролла — ни на 375, ни на 768, ни на 1280px.
    """
    paths = ["/", "/habits", "/profile", "/friends", "/goals", "/achievements", "/coach", "/stats"]
    for path in paths:
        for width in VIEWPORTS:
            demo_page.set_viewport_size({"width": width, "height": 900})
            demo_page.goto(f"{e2e_server}{path}")
            demo_page.wait_for_load_state("networkidle")

            page_overflow = demo_page.evaluate(
                "document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
            )
            assert not page_overflow, f"{path} при {width}px требует горизонтальный скролл"

            truncated = demo_page.evaluate(
                """() => {
                    const results = [];
                    document.querySelectorAll('*').forEach(el => {
                        if (el.scrollWidth > el.clientWidth + 2 && el.children.length === 0 && el.textContent.trim()) {
                            results.push(el.textContent.trim().slice(0, 40));
                        }
                    });
                    return results;
                }"""
            )
            assert truncated == [], f"{path} при {width}px: обрезанный текст {truncated}"
