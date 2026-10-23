"""E2e: de personenkiezer in het Nieuw-laptopformulier vindt ook leerkrachten.

Een leerkracht zonder Stamnummer in de Informat-export is gesleuteld op zijn
gebruikersnaam. Zonder kiezer moest je die sleutel uit het hoofd kennen; deze
test legt vast dat zoeken op naam volstaat en dat de juiste sleutel wordt gezet.
"""
import pytest

NAAM = "Zzztestleerkracht"
VOORNAAM = "Eva"
GEBRUIKERSNAAM = "eva.zzztestleerkracht"
POINTER = "998877"


@pytest.fixture()
def leerkracht(page, base_url):
    """Maak één leerkracht aan en ruim hem daarna weer op."""
    csv = (
        f"Naam;Voornaam;Gebruikersnaam;Pointer\n"
        f"{NAAM};{VOORNAAM};{GEBRUIKERSNAAM};{POINTER}\n"
    ).encode()
    resp = page.context.request.post(
        f"{base_url}/api/students/import?leerkracht=true",
        multipart={"file": {"name": "lk.csv", "mimeType": "text/csv", "buffer": csv}},
    )
    assert resp.ok, f"aanmaken leerkracht mislukt: {resp.status} {resp.text()}"
    yield
    page.context.request.delete(
        f"{base_url}/api/students", data={"stamnummers": [GEBRUIKERSNAAM]}
    )


def _open_nieuw_formulier(page, base_url):
    page.goto(base_url)
    # De tabbalk gebruikt role="tab", niet de impliciete button-rol.
    page.get_by_role("tab", name="Instellingen").click()
    # "+ Nieuw" staat ook in de Import-sectie; alleen die van Beheer laptops is zichtbaar.
    page.locator("button:visible", has_text="+ Nieuw").first.click()


def test_kiezer_vindt_leerkracht_op_naam(page, base_url, leerkracht):
    _open_nieuw_formulier(page, base_url)

    page.locator("#new-laptop-person").fill(NAAM.lower())

    optie = page.locator(".lt-person-option", has_text=NAAM).first
    optie.wait_for(state="visible", timeout=5000)
    # De kiezer toont de pointer, want deze leerkracht heeft geen stamnummer.
    assert POINTER in optie.inner_text()
    assert "Leerkracht" in optie.inner_text()


def test_kiezen_zet_de_gebruikersnaam_als_sleutel(page, base_url, leerkracht):
    _open_nieuw_formulier(page, base_url)

    page.locator("#new-laptop-person").fill(NAAM.lower())
    page.locator(".lt-person-option", has_text=NAAM).first.click()

    bevestiging = page.locator("text=Koppelt aan:")
    bevestiging.wait_for(state="visible", timeout=5000)
    assert GEBRUIKERSNAAM in bevestiging.inner_text()
