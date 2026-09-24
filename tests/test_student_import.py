"""Tests for CSV student import — both service layer and HTTP route."""

import io
from datetime import timedelta

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


# ── Leerkrachten ──────────────────────────────────────────────────────────────

def test_import_teachers_sets_flag(db_session):
    count = import_students_from_stream(
        db_session, _csv(_row("L001", klas="")), is_leerkracht=True
    )

    assert count == 1
    teacher = db_session.get(Student, "L001")
    assert teacher.is_leerkracht is True


def test_student_import_defaults_to_not_teacher(db_session):
    import_students_from_stream(db_session, _csv(_row("S100")))

    assert db_session.get(Student, "S100").is_leerkracht is False


def test_teacher_without_stamnummer_uses_gebruikersnaam(db_session):
    csv = io.StringIO("Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n")

    count = import_students_from_stream(db_session, csv, is_leerkracht=True)

    assert count == 1
    teacher = db_session.get(Student, "an.peeters")
    assert teacher is not None
    assert teacher.naam == "Peeters"
    assert teacher.is_leerkracht is True


def test_student_without_stamnummer_is_still_skipped(db_session):
    csv = io.StringIO("Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n")

    assert import_students_from_stream(db_session, csv) == 0


def test_teacher_import_headers_are_case_insensitive(db_session):
    csv = io.StringIO("NAAM ; voornaam;GEBRUIKERSNAAM\nJanssens;Tom;tom.janssens\n")

    import_students_from_stream(db_session, csv, is_leerkracht=True)

    teacher = db_session.get(Student, "tom.janssens")
    assert teacher.naam == "Janssens"
    assert teacher.voornaam == "Tom"


def test_teacher_import_does_not_convert_existing_student(db_session):
    import_students_from_stream(db_session, _csv(_row("X001", naam="Leerling")))

    count = import_students_from_stream(
        db_session, _csv(_row("X001", naam="Leerkracht")), is_leerkracht=True
    )

    assert count == 0
    student = db_session.get(Student, "X001")
    assert student.is_leerkracht is False
    assert student.naam == "Leerling"


def test_import_route_teachers(client, db_session):
    csv_bytes = b"Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n"

    resp = client.post(
        "/api/students/import?leerkracht=true",
        files={"file": ("leerkrachten.csv", csv_bytes, "text/csv")},
    )

    assert resp.status_code == 200
    assert resp.json()["imported"] == 1
    assert db_session.get(Student, "an.peeters").is_leerkracht is True


def test_uitgeschreven_is_scoped_per_group(client):
    """A teacher import must not flag students as uitgeschreven (and vice versa)."""
    client.post(
        "/api/students/import",
        files={"file": ("s.csv", f"{_CSV_HEADER}\n{_row('S200')}\n".encode(), "text/csv")},
    )
    client.post(
        "/api/students/import?leerkracht=true",
        files={"file": ("l.csv", b"Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n", "text/csv")},
    )

    html = client.get("/ui/students/manage").text

    assert "Uitgeschreven" not in html
    assert "badge-teacher" in html
    assert 'data-group="leerkracht"' in html
    assert 'data-group="leerling"' in html


def test_uitgeschreven_still_flags_students_missing_from_latest_import(client, db_session):
    import_students_from_stream(db_session, _csv(_row("S300"), _row("S301")))
    import_students_from_stream(db_session, _csv(_row("L300")), is_leerkracht=True)
    old = db_session.get(Student, "S300")
    old.last_import = old.last_import - timedelta(days=30)
    db_session.commit()

    html = client.get("/ui/students/list").text

    assert html.count("badge-old") == 1


def test_teacher_can_be_linked_to_laptop(client):
    client.post(
        "/api/students/import?leerkracht=true",
        files={"file": ("l.csv", b"Naam;Voornaam;Gebruikersnaam\nPeeters;An;an.peeters\n", "text/csv")},
    )

    resp = client.post(
        "/api/laptops/link",
        json={"stamnummer": "an.peeters", "serial_number": "SN-LK-1"},
    )

    assert resp.status_code == 200
    laptops = client.get("/api/laptops").json()
    assert any(l["serial_number"] == "SN-LK-1" for l in laptops)


def test_create_teacher_manually(client):
    resp = client.post("/api/students", json={"stamnummer": "lk.manual", "is_leerkracht": True})

    assert resp.status_code == 200
    assert resp.json()["is_leerkracht"] is True


def test_index_shows_teacher_import_and_filters(client):
    html = client.get("/").text

    assert "/ui/students/import?leerkracht=true" in html
    assert "__leerkrachten__" in html


# ── Leerkrachten-export (tab-gescheiden) ──────────────────────────────────────
# LET OP: deze fixture spiegelt de KOLOMSTRUCTUUR van de echte Informat-export,
# maar alle waarden zijn verzonnen. Plak hier nooit een rij uit een echte export:
# de kolommen StandaardPaswoord en Pincode bevatten dan werkende inloggegevens.
# Het domein school.example is gereserveerd (RFC 2606) en bestaat dus nooit echt.

_TEACHER_HEADER = (
    "Instellingsnummers\tNaam\tVoornaam\tRoepnaam\tGebruikersnaam\tStandaardPaswoord\t"
    "Pointer\tBetaalkaart\tBarcode\tPincode\tPointerZonderPrefix\tGebruikersnaam AD (kort)\t"
    "Gebruikersnaam AD\tGebruikersnaam O365\tGebruikersnaam Google\tAfkorting"
)
_TEACHER_ROW = (
    "099999\tVoorbeeld\tÉmile\t\temile.voorbeeld\tNietEchtPw1!\t999001\t\t99001\t99900199\t"
    "999001\temile.voorbeeld\temile.voorbeeld@school.example\temile.voorbeeld@school.example\t"
    "emile.voorbeeld@\tVOOEM"
)


def _teacher_csv() -> io.StringIO:
    return io.StringIO(f"{_TEACHER_HEADER}\n{_TEACHER_ROW}\n")


def test_real_teacher_export_is_imported(db_session):
    count = import_students_from_stream(db_session, _teacher_csv(), is_leerkracht=True)

    assert count == 1
    teacher = db_session.get(Student, "emile.voorbeeld")
    assert teacher.is_leerkracht is True
    assert teacher.naam == "Voorbeeld"
    assert teacher.voornaam == "Émile"
    assert teacher.afkorting == "VOOEM"
    assert teacher.instellingsnummer == "099999"
    assert teacher.pointer == "999001"


def test_teacher_export_passwords_are_not_stored(db_session):
    import_students_from_stream(db_session, _teacher_csv(), is_leerkracht=True)

    teacher = db_session.get(Student, "emile.voorbeeld")
    stored = {
        str(value) for value in vars(teacher).values() if isinstance(value, str)
    }
    assert "NietEchtPw1!" not in stored  # StandaardPaswoord
    assert "99900199" not in stored  # Pincode


def test_teacher_export_is_searchable_by_afkorting(client, db_session):
    import_students_from_stream(db_session, _teacher_csv(), is_leerkracht=True)

    html = client.get("/ui/students/manage").text

    assert "VOOEM" in html


def test_semicolon_and_comma_csv_still_work(db_session):
    import_students_from_stream(db_session, _csv(_row("S400")))
    import_students_from_stream(
        db_session,
        io.StringIO("Naam,Voornaam,Gebruikersnaam\nJanssens,Tom,tom.janssens\n"),
        is_leerkracht=True,
    )

    assert db_session.get(Student, "S400").naam == "Doe"
    assert db_session.get(Student, "tom.janssens").naam == "Janssens"
