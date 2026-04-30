"""Tests for POST /api/laptops/link."""

import pytest

from app.models.student import Student


# ── Helpers ───────────────────────────────────────────────────────────────────

def _add_student(session, stamnummer: str, naam: str = "Doe", voornaam: str = "John") -> Student:
    student = Student(stamnummer=stamnummer, naam=naam, voornaam=voornaam, klas="3A")
    session.add(student)
    session.commit()
    return student


def _link(client, stamnummer: str, serial: str, overwrite: bool = False):
    return client.post(
        "/api/laptops/link",
        json={
            "stamnummer": stamnummer,
            "serial_number": serial,
            "overwrite_existing": overwrite,
        },
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_link_laptop_to_student(client, db_session):
    _add_student(db_session, "S001")

    resp = _link(client, "S001", "ABC-001")

    assert resp.status_code == 200
    data = resp.json()
    assert data["stamnummer"] == "S001"
    assert data["serial_number"] == "ABC-001"
    assert data["eigen_laptop"] is False


def test_link_laptop_alphanumeric_serial(client, db_session):
    _add_student(db_session, "S002")

    resp = _link(client, "S002", "HP-NB-2024-XZ99")

    assert resp.status_code == 200
    assert resp.json()["serial_number"] == "HP-NB-2024-XZ99"


def test_link_laptop_returns_404_for_unknown_student(client, db_session):
    resp = _link(client, "UNKNOWN", "SER-999")

    assert resp.status_code == 404


def test_link_laptop_conflict_existing_serial(client, db_session):
    """A serial already linked to another student must return 409."""
    _add_student(db_session, "S010")
    _add_student(db_session, "S011")
    _link(client, "S010", "SHARED-001")

    resp = _link(client, "S011", "SHARED-001")

    assert resp.status_code == 409
    assert "requires_confirmation" not in resp.json().get("detail", {})


def test_link_laptop_requires_confirmation_when_student_already_has_laptop(client, db_session):
    """Linking a *different* serial to a student who already has one must return 409
    with requires_confirmation=True so the UI can prompt the user."""
    _add_student(db_session, "S020")
    _link(client, "S020", "FIRST-001")

    resp = _link(client, "S020", "SECOND-001")

    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["requires_confirmation"] is True
    assert "FIRST-001" in detail["existing_serials"]


def test_link_laptop_overwrites_after_confirmation(client, db_session):
    """With overwrite_existing=True the old laptop is replaced."""
    _add_student(db_session, "S030")
    _link(client, "S030", "OLD-001")

    resp = _link(client, "S030", "NEW-001", overwrite=True)

    assert resp.status_code == 200
    assert resp.json()["serial_number"] == "NEW-001"


def test_link_eigen_laptop(client, db_session):
    """Scanning 'eigen laptop' must create a record with serial=None and eigen_laptop=True."""
    _add_student(db_session, "S040")

    resp = _link(client, "S040", "eigen laptop")

    assert resp.status_code == 200
    data = resp.json()
    assert data["eigen_laptop"] is True
    assert data["serial_number"] is None


def test_link_eigen_laptop_overwrites_existing(client, db_session):
    """eigen laptop scan with overwrite=True replaces a regular laptop."""
    _add_student(db_session, "S050")
    _link(client, "S050", "REG-001")

    resp = _link(client, "S050", "eigen laptop", overwrite=True)

    assert resp.status_code == 200
    assert resp.json()["eigen_laptop"] is True


def test_multiple_students_can_each_have_eigen_laptop(client, db_session):
    """NULL serial_number must be allowed for multiple students simultaneously."""
    _add_student(db_session, "S060")
    _add_student(db_session, "S061")

    r1 = _link(client, "S060", "eigen laptop")
    r2 = _link(client, "S061", "eigen laptop")

    assert r1.status_code == 200
    assert r2.status_code == 200


# ── Unlink (INLEVEREN) ────────────────────────────────────────────────────────

def _unlink(client, laptop_id: int):
    return client.post(f"/api/laptops/{laptop_id}/unlink")


def test_unlink_sets_unlinked_at(client, db_session):
    """Scanning INLEVEREN must set unlinked_at on the laptop record."""
    _add_student(db_session, "S100")
    laptop_id = _link(client, "S100", "UNL-001").json()["id"]

    resp = _unlink(client, laptop_id)

    assert resp.status_code == 200
    assert resp.json()["unlinked_at"] is not None


def test_unlink_returns_404_for_unknown_laptop(client, db_session):
    resp = _unlink(client, 99999)

    assert resp.status_code == 404


def test_unlink_already_unlinked_returns_409(client, db_session):
    """Inleveren a laptop that is already ingeleverd must return 409."""
    _add_student(db_session, "S110")
    laptop_id = _link(client, "S110", "UNL-002").json()["id"]
    _unlink(client, laptop_id)

    resp = _unlink(client, laptop_id)

    assert resp.status_code == 409


# ── Reserve laptops ───────────────────────────────────────────────────────────


def _create_reserve(client, alias: str, serial: str | None = None):
    payload = {"is_reserve": True, "alias": alias}
    if serial:
        payload["serial_number"] = serial
    return client.post("/api/laptops", json=payload)


def test_create_reserve_laptop_without_stamnummer(client, db_session):
    """A reserve laptop must be creatable without a student (stamnummer=None)."""
    resp = _create_reserve(client, "Reserve-1", serial="RES-001")

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_reserve"] is True
    assert data["alias"] == "Reserve-1"
    assert data["serial_number"] == "RES-001"
    assert data["stamnummer"] is None


def test_create_reserve_laptop_without_serial(client, db_session):
    """Reserve laptop without serial number is allowed."""
    resp = _create_reserve(client, "Reserve-2")

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_reserve"] is True
    assert data["serial_number"] is None


def test_create_reserve_requires_alias(client, db_session):
    """Creating a reserve without alias must return 422."""
    resp = client.post("/api/laptops", json={"is_reserve": True})

    assert resp.status_code == 422


def test_create_normal_laptop_still_requires_stamnummer(client, db_session):
    """Normal (non-reserve) laptop creation still needs a student."""
    resp = client.post("/api/laptops", json={"serial_number": "ABC123"})

    assert resp.status_code in (404, 422)


def test_list_laptops_kind_filter_reserve(client, db_session):
    """GET /api/laptops?kind=reserve returns only reserve laptops."""
    _add_student(db_session, "S200")
    client.post("/api/laptops", json={"serial_number": "NORM-001", "stamnummer": "S200"})
    _create_reserve(client, "Reserve-X", serial="RES-X01")

    resp = client.get("/api/laptops?kind=reserve")

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["is_reserve"] is True
    assert items[0]["alias"] == "Reserve-X"


def test_list_laptops_kind_filter_normal(client, db_session):
    """GET /api/laptops?kind=normal excludes reserve laptops."""
    _add_student(db_session, "S210")
    client.post("/api/laptops", json={"serial_number": "NORM-002", "stamnummer": "S210"})
    _create_reserve(client, "Reserve-Y")

    resp = client.get("/api/laptops?kind=normal")

    assert resp.status_code == 200
    serials = [item["serial_number"] for item in resp.json()]
    assert "NORM-002" in serials
    aliases = [item.get("alias") for item in resp.json()]
    assert "Reserve-Y" not in aliases


def test_available_reserves_endpoint(client, db_session):
    """GET /api/laptops/reserves/available returns all reserve laptops."""
    _create_reserve(client, "Res-A", serial="RES-A")
    _create_reserve(client, "Res-B", serial="RES-B")

    resp = client.get("/api/laptops/reserves/available")

    assert resp.status_code == 200
    aliases = [r["alias"] for r in resp.json()]
    assert "Res-A" in aliases
    assert "Res-B" in aliases


def test_update_laptop_alias(client, db_session):
    """PUT /api/laptops/{id} can update the alias of a reserve laptop."""
    laptop_id = _create_reserve(client, "Oud-Alias", serial="RES-UP").json()["id"]

    resp = client.put(f"/api/laptops/{laptop_id}", json={"alias": "Nieuw-Alias"})

    assert resp.status_code == 200
    assert resp.json()["alias"] == "Nieuw-Alias"
