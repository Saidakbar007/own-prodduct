"""E2e: страница /hero открывается из сайдбара и показывает героя и 5 личностей."""


def test_hero_link_in_sidebar_navigates_to_hero_page(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(f"{e2e_server}/")
    demo_page.wait_for_load_state("networkidle")

    sidebar = demo_page.locator("aside").first
    sidebar.locator('a[href="/hero"]').first.click()

    demo_page.wait_for_url("**/hero")
    demo_page.wait_for_load_state("networkidle")

    for persona_name in ("Воин", "Мудрец", "Монах", "Целитель", "Бард"):
        assert persona_name in demo_page.content()

    svg = demo_page.locator("svg[aria-label='Диаграмма сфер героя']").first
    assert svg.is_visible()
