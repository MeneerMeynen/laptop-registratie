"""Tests for the printable gebruiksovereenkomst (GET /contract/{stamnummer})."""
from datetime import date, datetime

from app.models.laptop import Laptop
from app.models.student import Student
from app.services.contract_service import datum_nl, schooljaar


def _add_person(session, stamnummer: str, **kwargs) -> Student:
    person = Student(stamnummer=stamnummer, **kwargs)
    session.add(person)
    session.commit()
    return person


def _link(client, stamnummer: str, serial: str) -> dict:
    resp = client.post("/api/laptops/link",
                       json={"stamnummer": stamnummer, "serial_number": serial})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_contract_leerling(client, db_session):
    _add_person(db_session, "CON1", naam="Janssens", voornaam="Mila", klas="4B")
    _link(client, "CON1", "SN-CON1")

    resp = client.get("/contract/CON1")

    assert resp.status_code == 200
    html = resp.text
    assert "GEBRUIKSOVEREENKOMST" in html
    assert "Mila Janssens" in html
    assert "4B" in html
    assert "SN-CON1" in html
    assert "Ouder/wettelijke vertegenwoordiger" in html
    assert "€100" in html
    assert "juni van het 6de jaar" in html
    assert "Personeelslid" not in html
    assert f"schooljaar {schooljaar(date.today())}" in html


def test_contract_not_for_leerkracht(client, db_session):
    _add_person(db_session, "jan.peeters", naam="Peeters", voornaam="Jan",
                afkorting="PEEJA", is_leerkracht=True)
    _link(client, "jan.peeters", "SN-LK1")

    assert client.get("/contract/jan.peeters").status_code == 404


def test_contract_uses_link_date(client, db_session):
    _add_person(db_session, "CON2", naam="Claes", voornaam="Lotte", klas="5A")
    data = _link(client, "CON2", "SN-CON2")
    laptop = db_session.get(Laptop, data["id"])
    laptop.linked_at = datetime(2026, 9, 3, 10, 0)
    db_session.commit()

    html = client.get("/contract/CON2").text

    assert "Opgemaakt te Lommel, op 3 september 2026" in html
    assert "schooljaar 2026-2027" in html


def test_contract_without_laptop_404(client, db_session):
    _add_person(db_session, "CON3", naam="Wouters", voornaam="Noor", klas="3C")
    assert client.get("/contract/CON3").status_code == 404


def test_contract_eigen_laptop_404(client, db_session):
    _add_person(db_session, "CON4", naam="Maes", voornaam="Lars", klas="6A")
    _link(client, "CON4", "eigen laptop")
    assert client.get("/contract/CON4").status_code == 404


def test_contract_unlinked_laptop_404(client, db_session):
    _add_person(db_session, "CON5", naam="Goossens", voornaam="Emma", klas="4A")
    data = _link(client, "CON5", "SN-CON5")
    assert client.post(f"/api/laptops/{data['id']}/unlink", json={}).status_code == 200
    assert client.get("/contract/CON5").status_code == 404


def test_contract_unknown_person_404(client):
    assert client.get("/contract/BESTAATNIET").status_code == 404


def test_contract_requires_login(anon_client):
    resp = anon_client.get("/contract/CON1", follow_redirects=False)
    assert resp.status_code in (303, 401)


def test_schooljaar_and_datum():
    assert schooljaar(date(2026, 9, 1)) == "2026-2027"
    assert schooljaar(date(2027, 3, 15)) == "2026-2027"
    assert schooljaar(date(2027, 8, 20)) == "2027-2028"
    assert datum_nl(date(2026, 9, 1)) == "1 september 2026"
