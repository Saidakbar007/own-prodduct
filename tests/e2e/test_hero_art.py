"""
E2e: 3D-арт героя/личностей на /hero и на главной — не обрезан/не
растянут (нет переполнения) на 375px в обеих темах, вес страницы /hero
в бюджете ~1.5 МБ.
"""

PAGE_WEIGHT_BUDGET_BYTES = 1.5 * 1024 * 1024


def test_hero_page_weight_within_budget(demo_page, e2e_server):
    total = {"bytes": 0}

    def on_response(response):
        try:
            total["bytes"] += len(response.body())
        except Exception:
            pass

    demo_page.on("response", on_response)
    demo_page.goto(f"{e2e_server}/hero")
    demo_page.wait_for_load_state("networkidle")

    assert total["bytes"] < PAGE_WEIGHT_BUDGET_BYTES, f"/hero весит {total['bytes'] / 1024 / 1024:.2f} МБ"


def test_hero_art_not_cropped_or_stretched_at_375px(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 375, "height": 1400})
    demo_page.goto(f"{e2e_server}/hero")
    demo_page.wait_for_load_state("networkidle")

    overflow = demo_page.evaluate(
        "document.documentElement.scrollWidth > document.documentElement.clientWidth + 2"
    )
    assert not overflow

    hero_img = demo_page.locator("img[alt='Герой']").first
    box = hero_img.bounding_box()
    assert box is not None
    assert box["width"] > 0 and box["height"] > 0

    natural = hero_img.evaluate("el => [el.naturalWidth, el.naturalHeight]")
    assert natural[0] > 0 and natural[1] > 0
    # object-fit: contain должен сохранять пропорции — отношение сторон
    # отрисованного блока близко к собственным пропорциям картинки
    rendered_ratio = box["width"] / box["height"]
    natural_ratio = natural[0] / natural[1]
    assert abs(rendered_ratio - natural_ratio) / natural_ratio < 0.05


def test_hero_art_visible_in_both_themes(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/hero")
    demo_page.wait_for_load_state("networkidle")

    for theme in ("light", "dark"):
        demo_page.evaluate(f"window.__applyTheme('{theme}')")
        hero_img = demo_page.locator("img[alt='Герой']").first
        assert hero_img.is_visible()

        persona_imgs = demo_page.locator("[data-persona] img")
        assert persona_imgs.count() == 5
        for i in range(5):
            assert persona_imgs.nth(i).is_visible()


def test_homepage_hero_image_next_to_pentagon(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/")
    demo_page.wait_for_load_state("networkidle")

    hero_img = demo_page.locator("img[alt='Герой']").first
    assert hero_img.is_visible()
    svg = demo_page.locator("svg[aria-label='Диаграмма сфер героя']").first
    assert svg.is_visible()
