"""E2E: дизайн-токены премиального тёмного дизайна реально применяются в обеих темах."""


def _css_var(page, name):
    return page.evaluate(f"getComputedStyle(document.documentElement).getPropertyValue('{name}').trim()")


def test_light_theme_tokens(demo_page, e2e_server):
    demo_page.goto(e2e_server)
    demo_page.evaluate("window.__applyTheme('light')")

    assert _css_var(demo_page, "--bg").lower() == "#f4f5f7"
    assert _css_var(demo_page, "--card").lower() == "#ffffff"
    assert _css_var(demo_page, "--accent").lower() == "#17985f"
    assert _css_var(demo_page, "--coin").lower() == "#a86a12"


def test_dark_theme_tokens(demo_page, e2e_server):
    demo_page.goto(e2e_server)
    demo_page.evaluate("window.__applyTheme('dark')")

    assert _css_var(demo_page, "--bg").lower() == "#0b0d10"
    assert _css_var(demo_page, "--card").lower() == "#171c22"
    assert _css_var(demo_page, "--accent").lower() == "#82e6b0"
    assert _css_var(demo_page, "--coin").lower() == "#d7a33e"


def test_no_purple_gradient_in_header(demo_page, e2e_server):
    demo_page.goto(e2e_server)
    header = demo_page.locator("header").first
    bg_image = header.evaluate("e => getComputedStyle(e).backgroundImage")
    assert bg_image == "none"


def test_card_has_thin_border_and_14px_radius(demo_page, e2e_server):
    demo_page.goto(f"{e2e_server}/habits")
    demo_page.wait_for_load_state("networkidle")

    card = demo_page.locator("text=Новая привычка").locator("xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' card ')][1]")
    styles = card.evaluate("e => { var s = getComputedStyle(e); return [s.borderRadius, s.borderWidth, s.boxShadow]; }")
    radius, border_width, box_shadow = styles
    assert radius == "14px"
    assert border_width == "1px"
    assert box_shadow == "none"  # без тяжёлых теней


def test_body_uses_manrope_font(demo_page, e2e_server):
    demo_page.goto(e2e_server)
    font = demo_page.evaluate("getComputedStyle(document.body).fontFamily")
    assert "Manrope" in font
