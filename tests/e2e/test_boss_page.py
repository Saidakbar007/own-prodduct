"""E2e: страница /boss открывается из меню и показывает статус блокировки/группы."""


def test_boss_link_navigates_and_shows_status(demo_page, e2e_server):
    demo_page.set_viewport_size({"width": 1280, "height": 900})
    demo_page.goto(f"{e2e_server}/")
    demo_page.wait_for_load_state("networkidle")

    demo_page.locator("[data-more-toggle]").first.click()
    menu = demo_page.locator(".more-menu.open:visible").first
    menu.wait_for(state="visible", timeout=3000)
    menu.locator('a[href="/boss"]').first.click()

    demo_page.wait_for_url("**/boss")
    demo_page.wait_for_load_state("networkidle")
    assert "Босс недели" in demo_page.content()
