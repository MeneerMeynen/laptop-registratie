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


def test_relinking_same_laptop_is_idempotent(client, db_session):
    """Re-scanning the same laptop for the same student must not create a new
    history record each time (regression: duplicate uitleengeschiedenis entries)."""
    from app.models.laptop import Laptop

    _add_student(db_session, "S070")
    first = _link(client, "S070", "REPEAT-001")
    assert first.status_code == 200

    second = _link(client, "S070", "REPEAT-001")
    third = _link(client, "S070", "REPEAT-001")

    assert second.status_code == 200
    assert third.status_code == 200
    # Same record returned every time, none of them closed.
    assert second.json()["id"] == first.json()["id"]
    assert third.json()["id"] == first.json()["id"]
    assert second.json()["unlinked_at"] is None

    rows = (
        db_session.query(Laptop)
        .filter(Laptop.serial_number == "REPEAT-001")
        .all()
    )
    assert len(rows) == 1


def test_relinking_same_eigen_laptop_is_idempotent(client, db_session):
    """Re-scanning 'eigen laptop' for a student who already has one is a no-op."""
    from app.models.laptop import Laptop

    _add_student(db_session, "S071")
    first = _link(client, "S071", "eigen laptop")
    second = _link(client, "S071", "eigen laptop")

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]

    rows = (
        db_session.query(Laptop)
        .filter(Laptop.stamnummer == "S071", Laptop.eigen_laptop.is_(True))
        .all()
    )
    assert len(rows) == 1


def test_multiple_students_can_each_have_eigen_laptop(client, db_session):
    """NULL serial_number must be allowed for multiple students simultaneously."""
    _add_student(db_session, "S060")
    _add_student(db_session, "S061")

    r1 = _link(client, "S060", "eigen laptop")
    r2 = _link(client, "S061", "eigen laptop")

    assert r1.status_code == 200
    assert r2.status_code == 200


# ── Unlink (INLEVEREN) ────────────────────────────────────────────────────────

def _unlink(client, laptop_id: int, hoes: bool = True, oplader: bool = True):
    return client.post(
        f"/api/laptops/{laptop_id}/unlink",
        json={"hoes_ingeleverd": hoes, "oplader_ingeleverd": oplader},
    )


def test_unlink_sets_unlinked_at(client, db_session):
    """Scanning INLEVEREN must set unlinked_at on the laptop record."""
    from app.models.laptop_issue import LaptopIssue

    _add_student(db_session, "S100")
    laptop_id = _link(client, "S100", "UNL-001").json()["id"]

    resp = _unlink(client, laptop_id)

    assert resp.status_code == 200
    data = resp.json()
    assert data["unlinked_at"] is not None
    assert data["hoes_ingeleverd"] is True
    assert data["oplader_ingeleverd"] is True
    # No issue created when both accessories are present.
    assert db_session.query(LaptopIssue).filter_by(serial_number="UNL-001").count() == 0


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


def test_unlink_without_body_uses_defaults(client, db_session):
    """Backward compatibility: POST /unlink without body still works."""
    _add_student(db_session, "S105")
    laptop_id = _link(client, "S105", "UNL-NB").json()["id"]

    resp = client.post(f"/api/laptops/{laptop_id}/unlink")

    assert resp.status_code == 200
    assert resp.json()["hoes_ingeleverd"] is True
    assert resp.json()["oplader_ingeleverd"] is True


def test_unlink_with_missing_accessories_creates_issue(client, db_session):
    """When an accessory is missing, an issue must be created automatically."""
    from app.models.laptop import Laptop
    from app.models.laptop_issue import LaptopIssue

    _add_student(db_session, "S120")
    laptop_id = _link(client, "S120", "UNL-MISS").json()["id"]

    resp = _unlink(client, laptop_id, hoes=False, oplader=True)

    assert resp.status_code == 200
    data = resp.json()
    assert data["hoes_ingeleverd"] is False
    assert data["oplader_ingeleverd"] is True

    laptop = db_session.get(Laptop, laptop_id)
    assert laptop.hoes_ingeleverd is False
    assert laptop.oplader_ingeleverd is True

    issues = db_session.query(LaptopIssue).filter_by(serial_number="UNL-MISS").all()
    assert len(issues) == 1
    assert issues[0].category == "Accessoires"
    assert issues[0].status == "aangemeld"
    assert "hoes" in issues[0].description.lower()
    assert "oplader" not in issues[0].description.lower()


def test_unlink_with_both_accessories_missing_lists_both_in_issue(client, db_session):
    from app.models.laptop_issue import LaptopIssue

    _add_student(db_session, "S121")
    laptop_id = _link(client, "S121", "UNL-BOTH").json()["id"]

    resp = _unlink(client, laptop_id, hoes=False, oplader=False)

    assert resp.status_code == 200
    issues = db_session.query(LaptopIssue).filter_by(serial_number="UNL-BOTH").all()
    assert len(issues) == 1
    desc = issues[0].description.lower()
    assert "hoes" in desc
    assert "oplader" in desc


def test_relink_resets_accessory_flags(client, db_session):
    """Heruitgifte aan een nieuwe leerling: vlaggen terug op True (nieuwe accessoires uitgereikt)."""
    from app.models.laptop import Laptop

    _add_student(db_session, "S130")
    _add_student(db_session, "S131")
    first_id = _link(client, "S130", "UNL-RST").json()["id"]
    _unlink(client, first_id, hoes=False, oplader=False)

    second_resp = _link(client, "S131", "UNL-RST")
    assert second_resp.status_code == 200
    second_id = second_resp.json()["id"]
    assert second_id != first_id  # new history row

    new_record = db_session.get(Laptop, second_id)
    assert new_record.hoes_ingeleverd is True
    assert new_record.oplader_ingeleverd is True


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


# ── CSV export ────────────────────────────────────────────────────────────────


def test_export_laptops_returns_csv(client, db_session):
    """GET /api/laptops/export returns a CSV attachment with a header row."""
    _add_student(db_session, "S300", naam="Jansen", voornaam="Lotte")
    _link(client, "S300", "EXP-001")

    resp = client.get("/api/laptops/export")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.text
    assert "Serienummer;Type;Leerling" in body
    assert "EXP-001" in body
    assert "Lotte Jansen" in body


def test_export_laptops_includes_accessory_status(client, db_session):
    """Ingeleverde laptops must show ja/nee for hoes and oplader in the export."""
    _add_student(db_session, "S310")
    laptop_id = _link(client, "S310", "EXP-MISS").json()["id"]
    _unlink(client, laptop_id, hoes=False, oplader=True)

    resp = client.get("/api/laptops/export")

    assert resp.status_code == 200
    line = next(li for li in resp.text.splitlines() if "EXP-MISS" in li)
    cols = line.split(";")
    # Kolommen: 7 = Status, 8 = Hoes ingeleverd, 9 = Oplader ingeleverd
    assert cols[7] == "Inactief"
    assert cols[8] == "nee"
    assert cols[9] == "ja"


def test_export_laptops_respects_kind_filter(client, db_session):
    """The kind filter must scope the export the same way the list does."""
    _add_student(db_session, "S320")
    _link(client, "S320", "EXP-NORM")
    _create_reserve(client, "Reserve-Exp", serial="EXP-RES")

    resp = client.get("/api/laptops/export?kind=reserve")

    assert resp.status_code == 200
    body = resp.text
    assert "EXP-RES" in body
    assert "EXP-NORM" not in body
