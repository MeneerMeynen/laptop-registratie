"""Tests for student deletion and list ordering."""

from app.models.laptop import Laptop
from app.models.student import Student
from app.services.student_service import delete_students_by_stamnummers
from app.services.laptop_service import list_students


# ── Helpers ───────────────────────────────────────────────────────────────────

def _add_student(session, stamnummer: str, naam: str = "Doe", voornaam: str = "A") -> Student:
    s = Student(stamnummer=stamnummer, naam=naam, voornaam=voornaam, klas="3A")
    session.add(s)
    session.commit()
    return s


def _add_laptop(session, stamnummer: str, serial: str) -> Laptop:
    lap = Laptop(serial_number=serial, stamnummer=stamnummer, eigen_laptop=False)
    session.add(lap)
    session.commit()
    return lap


# ── Service-layer tests ───────────────────────────────────────────────────────

def test_delete_students_returns_correct_count(db_session):
    _add_student(db_session, "D001")
    _add_student(db_session, "D002")
    _add_student(db_session, "D003")

    deleted = delete_students_by_stamnummers(db_session, ["D001", "D002"])

    assert deleted == 2
    remaining = db_session.query(Student).all()
    assert len(remaining) == 1
    assert remaining[0].stamnummer == "D003"


def test_delete_cascades_to_laptops(db_session):
    """Deleting a student must also remove their linked laptops."""
    _add_student(db_session, "D010")
    _add_laptop(db_session, "D010", "SN-CASCADE-01")

    assert db_session.query(Laptop).filter_by(stamnummer="D010").count() == 1

    delete_students_by_stamnummers(db_session, ["D010"])

    assert db_session.query(Laptop).filter_by(stamnummer="D010").count() == 0


def test_delete_ignores_empty_list(db_session):
    _add_student(db_session, "D020")

    deleted = delete_students_by_stamnummers(db_session, [])

    assert deleted == 0
    assert db_session.query(Student).count() == 1


def test_list_students_sorted_by_naam_then_voornaam(db_session):
    _add_student(db_session, "L001", naam="Zorro", voornaam="A")
    _add_student(db_session, "L002", naam="Aardig", voornaam="Z")
    _add_student(db_session, "L003", naam="Aardig", voornaam="A")

    students = list_students(db_session)
    names = [(s.naam, s.voornaam) for s in students]

    assert names == [("Aardig", "A"), ("Aardig", "Z"), ("Zorro", "A")]


# ── HTTP route tests ──────────────────────────────────────────────────────────

def test_delete_route(client, db_session):
    _add_student(db_session, "R001")
    _add_student(db_session, "R002")

    resp = client.request(
        "DELETE",
        "/api/students",
        json={"stamnummers": ["R001", "R002"]},
    )

    assert resp.status_code == 200
    assert resp.json()["deleted"] == 2


def test_get_students_route(client, db_session):
    _add_student(db_session, "G001", naam="Alpha")
    _add_student(db_session, "G002", naam="Beta")

    resp = client.get("/api/students")

    assert resp.status_code == 200
    stamnummers = [s["stamnummer"] for s in resp.json()]
    assert "G001" in stamnummers
    assert "G002" in stamnummers
