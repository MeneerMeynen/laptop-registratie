"""Tests for CSV student import — both service layer and HTTP route."""

import io

from app.models.student import Student
from app.services.student_import import import_students_from_stream

# ── Minimal valid CSV fixture ─────────────────────────────────────────────────

_CSV_HEADER = "Instellingsnummer;Naam;Voornaam;Klas;Klascode;Klasnummer;Gebruikersnaam;Pointer;Stamnummer"

def _csv(*rows: str) -> io.StringIO:
    """Build a semicolon-delimited CSV stream from header + row strings."""
    lines = [_CSV_HEADER] + list(rows)
    return io.StringIO("\n".join(lines))


def _row(stamnummer: str, naam: str = "Doe", voornaam: str = "John", klas: str = "3A") -> str:
    return f"12345;{naam};{voornaam};{klas};KL01;1;user_{stamnummer};PTR1;{stamnummer}"


# ── Service-layer tests ───────────────────────────────────────────────────────

def test_import_from_stream_inserts_students(db_session):
    count = import_students_from_stream(db_session, _csv(_row("S001"), _row("S002")))

    assert count == 2
    students = db_session.query(Student).all()
    assert len(students) == 2
    stamnummers = {s.stamnummer for s in students}
    assert {"S001", "S002"} == stamnummers


def test_import_upserts_existing_students(db_session):
    """Re-importing the same stamnummer must update, not duplicate."""
    import_students_from_stream(db_session, _csv(_row("S010", naam="OldName")))
    count = import_students_from_stream(db_session, _csv(_row("S010", naam="NewName")))

    assert count == 1
    students = db_session.query(Student).filter_by(stamnummer="S010").all()
    assert len(students) == 1
    assert students[0].naam == "NewName"


def test_import_sets_last_import_timestamp(db_session):
    import_students_from_stream(db_session, _csv(_row("S020")))

    student = db_session.get(Student, "S020")
    assert student is not None
    assert student.last_import is not None


# ── HTTP route test ───────────────────────────────────────────────────────────

def test_import_route_returns_imported_count(client):
    csv_bytes = (
        f"{_CSV_HEADER}\n"
        f"{_row('S030')}\n"
        f"{_row('S031')}\n"
    ).encode("utf-8")

    resp = client.post(
        "/api/students/import",
        files={"file": ("students.csv", csv_bytes, "text/csv")},
    )

    assert resp.status_code == 200
    assert resp.json()["imported"] == 2


def test_import_route_rejects_non_csv(client):
    resp = client.post(
        "/api/students/import",
        files={"file": ("students.txt", b"some data", "text/plain")},
    )

    assert resp.status_code == 400
