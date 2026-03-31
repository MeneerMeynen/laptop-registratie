from playwright.sync_api import Page, expect


def test_clear_barcode_wipes_input(page: Page, base_url: str):
    """Onbruikbare data in het veld, daarna CLEAR scannen wist het veld.

    Een scanner voegt tekst toe aan wat er al staat — er wordt niet eerst
    gewist. Na 'sdkfjsdkfj' staat er dus 'sdkfjsdkfjCLEAR' in het veld
    op het moment dat Alpine.js reageert.
    """
    page.goto(base_url)

    serial_input = page.locator("#serial_number")

    # Stap 1: onbruikbare data staat in het veld (geen Enter gescand)
    serial_input.fill("sdkfjsdkfj")
    expect(serial_input).to_have_value("sdkfjsdkfj")

    # Stap 2: scanner voegt 'CLEAR' toe achter de bestaande inhoud
    serial_input.press_sequentially("CLEAR")
    # Veld bevat nu tijdelijk 'sdkfjsdkfjCLEAR'; Alpine.js detecteert
    # endsWith('CLEAR') en wist serialValue.
    expect(serial_input).to_have_value("")
