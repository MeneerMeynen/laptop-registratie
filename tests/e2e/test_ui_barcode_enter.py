from playwright.sync_api import Page, expect


def test_barcode_enter_without_student_shows_error(page: Page, base_url: str):
    """Barcode intypen en Enter drukken zonder leerling geeft foutmelding.

    Simuleert een scanner die een serienummer invoert gevolgd door Enter.
    Omdat nog geen leerling geselecteerd is, moet submitLink() een fout tonen.
    """
    page.goto(base_url)

    page.get_by_role("tab", name="Registreer").click()

    serial_input = page.locator("#serial_number")
    serial_input.fill("HP-NB-2024-XZ99")
    serial_input.press("Enter")

    expect(page.locator(".reg-main .status")).to_have_text("Selecteer eerst een leerling.")


def test_barcode_enter_clears_field_on_escape(page: Page, base_url: str):
    """Escape wist het invoerveld na het typen van een barcode."""
    page.goto(base_url)

    page.get_by_role("tab", name="Registreer").click()

    serial_input = page.locator("#serial_number")
    serial_input.fill("HP-NB-2024-XZ99")
    expect(serial_input).to_have_value("HP-NB-2024-XZ99")

    serial_input.press("Escape")

    expect(serial_input).to_have_value("")
