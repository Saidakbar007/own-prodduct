"""E2e: магазин открывается из сайдбара и показывает товары по слотам."""


def test_shop_link_navigates_and_shows_catalog(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(f"{e2e_server}/")
    demo_page.wait_for_load_state("networkidle")

    sidebar = demo_page.locator("aside").first
    sidebar.locator('a[href="/shop"]').first.click()

    demo_page.wait_for_url("**/shop")
    demo_page.wait_for_load_state("networkidle")

    for slot_label in ("Фон профиля", "Рамка аватара", "Титул", "Эффект отметки", "Заморозка серии"):
        assert slot_label in demo_page.content()
