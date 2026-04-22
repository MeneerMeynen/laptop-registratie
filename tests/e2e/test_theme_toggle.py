from playwright.sync_api import Page, expect


def test_theme_toggle_switches_to_light(page: Page, base_url: str):
    """Klikken op de toggle past data-theme="light" toe op <html>."""
    page.goto(base_url)

    # Default theme is dark
    expect(page.locator("html")).not_to_have_attribute("data-theme", "light")

    page.locator(".theme-toggle").click()

    expect(page.locator("html")).to_have_attribute("data-theme", "light")


def test_theme_toggle_switches_back_to_dark(page: Page, base_url: str):
    """Twee keer klikken keert terug naar dark."""
    page.goto(base_url)

    toggle = page.locator(".theme-toggle")
    toggle.click()
    toggle.click()

    expect(page.locator("html")).to_have_attribute("data-theme", "dark")


def test_theme_persists_after_reload(page: Page, base_url: str):
    """Light theme blijft na een page reload (via localStorage)."""
    page.goto(base_url)

    page.locator(".theme-toggle").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")

    page.reload()

    expect(page.locator("html")).to_have_attribute("data-theme", "light")
