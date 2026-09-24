"""Volledige flow in de browser: import → koppelen → ticket → opvolging → foto-pagina."""
from playwright.sync_api import Page, expect

CSV = (
    "Instellingsnummer;Naam;Voornaam;Klas;Klascode;Klasnummer;Gebruikersnaam;Pointer;Stamnummer\n"
    "1;Aerts;Nina;5C;5C;1;nina.aerts;1;E2E001\n"
    "1;Bosmans;Jef;5C;5C;2;jef.bosmans;2;E2E002\n"
)


def test_full_flow(page: Page, base_url: str):
    page.goto(base_url)

    # 1. Leerlingen importeren via de HTMX-upload (CSRF-token via htmx:configRequest).
    page.get_by_role("tab", name="Instellingen").click()
    page.set_input_files("#student-import-file", files=[{"name": "e2e.csv", "mimeType": "text/csv", "buffer": CSV.encode()}])
    expect(page.locator("#import-result")).to_contain_text("2 student(en) geïmporteerd")

    # 2. Laptop koppelen op het Registreer-tabblad (fetch → /api/laptops/link).
    page.get_by_role("tab", name="Registreer").click()
    page.locator(".student-option[data-stamnummer=E2E001]").click()
    serial = page.locator("#serial_number")
    serial.fill("E2E-SN-001")
    serial.press("Enter")
    expect(page.locator(".student-option[data-stamnummer=E2E001]")).to_contain_text("E2E-SN-001")

    # 3. Nieuw ticket via de modal (fetch → POST /api/laptop-issues).
    page.get_by_role("tab", name="Tickets").click()
    page.get_by_role("button", name="+ Defect").click()
    page.fill("#new-issue-serial", "E2E-SN-001")
    page.fill("#new-issue-description", "Scherm flikkert")
    page.get_by_role("button", name="Opslaan").click()
    expect(page.get_by_text("Het probleem is geregistreerd")).to_be_visible()
    page.get_by_role("button", name="Klaar").click()
    item = page.locator(".lt-item[data-serial=E2E-SN-001]")
    expect(item).to_be_visible()

    # 4. Detail openen en een opvolging toevoegen (HTMX POST).
    item.click()
    expect(page.locator("#lt-detail")).to_contain_text("Scherm flikkert")
    expect(page.locator("#lt-detail")).to_contain_text("Nina Aerts")
    page.fill("#lt-detail .lt-entry-form input[name=text]", "Aangemeld bij hersteller")
    page.click("#lt-detail .lt-entry-form button[type=submit]")
    expect(page.locator("#lt-detail .lt-entries")).to_contain_text("Aangemeld bij hersteller")

    # 5. Status wijzigen naar Open (fetch PATCH).
    page.locator("#lt-detail .lt-status-btn-open").first.click()
    expect(page.locator("#lt-detail .lt-status-btn-open.is-active")).to_be_visible()


def test_photo_page_loads_scanner(page: Page, base_url: str):
    logs = []
    page.on("console", lambda m: logs.append(m.text))
    page.goto(f"{base_url}/photos")
    expect(page.locator(".back-link")).to_be_visible()
    page.wait_for_function("window.__zxingReadBarcodes !== undefined", timeout=15000)
    assert any("zxing-wasm] geladen OK" in l for l in logs)
