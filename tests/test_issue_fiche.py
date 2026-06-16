"""Tests for the printable defect-/herstelfiche page (GET /laptop-issues/{id}/fiche)."""
from app.models.student import Student


# ── Helpers ───────────────────────────────────────────────────────────────────


def _add_student(session, stamnummer: str, naam: str = "Janssens",
                 voornaam: str = "Mila", klas: str = "4B") -> Student:
    student = Student(stamnummer=stamnummer, naam=naam, voornaam=voornaam, klas=klas)
    session.add(student)
    session.commit()
    return student


def _create_reserve(client, alias: str, serial: str) -> dict:
    resp = client.post("/api/laptops", json={"is_reserve": True, "alias": alias,
                                             "serial_number": serial})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _link_laptop(client, stamnummer: str, serial: str) -> dict:
    resp = client.post("/api/laptops/link",
                       json={"stamnummer": stamnummer, "serial_number": serial})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create_issue(client, serial: str, **kwargs) -> dict:
    payload = {"serial_number": serial, "description": "Scherm kapot",
               "reported_date": "2026-04-30"}
    payload.update(kwargs)
    resp = client.post("/api/laptop-issues", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_fiche_renders_all_ticket_data(client, db_session):
    _add_student(db_session, "FICHE1", naam="Janssens", voornaam="Mila", klas="4B")
    _link_laptop(client, "FICHE1", "LAPTOP-FICHE1")
    reserve = _create_reserve(client, "Reserve-7", "RES-7")
    issue = _create_issue(client, "LAPTOP-FICHE1", description="Toetsenbord defect",
                          category="Toetsenbord", reserve_laptop_id=reserve["id"])

    resp = client.get(f"/laptop-issues/{issue['id']}/fiche")

    assert resp.status_code == 200
    html = resp.text
    assert "Defect fiche" in html
    assert "Herstel Fiche" in html
    # Leerling- en toestelgegevens (bovenste helft)
    assert "Mila" in html and "Janssens" in html
    assert "4B" in html
    assert "LAPTOP-FICHE1" in html
    assert "Toetsenbord" in html
    assert "Toetsenbord defect" in html
    # Reserve-toestel (onderste helft)
    assert "In te leveren reserve toestel" in html
    assert "RES-7" in html


def test_fiche_without_reserve_shows_blank_field(client, db_session):
    _add_student(db_session, "FICHE2")
    _link_laptop(client, "FICHE2", "LAPTOP-FICHE2")
    issue = _create_issue(client, "LAPTOP-FICHE2")

    resp = client.get(f"/laptop-issues/{issue['id']}/fiche")

    assert resp.status_code == 200
    assert "In te leveren reserve toestel" in resp.text


def test_fiche_unknown_issue_returns_404(client, db_session):
    resp = client.get("/laptop-issues/999999/fiche")
    assert resp.status_code == 404
