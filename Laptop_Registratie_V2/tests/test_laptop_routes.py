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
