"""Tests for the reserve-laptop flow in laptop issue tracking."""
import pytest

from app.models.student import Student


# ── Helpers ───────────────────────────────────────────────────────────────────


def _add_student(session, stamnummer: str, naam: str = "Doe", voornaam: str = "John") -> Student:
    student = Student(stamnummer=stamnummer, naam=naam, voornaam=voornaam, klas="3A")
    session.add(student)
    session.commit()
    return student


def _create_reserve(client, alias: str, serial: str | None = None) -> dict:
    payload = {"is_reserve": True, "alias": alias}
    if serial:
        payload["serial_number"] = serial
    resp = client.post("/api/laptops", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _link_laptop(client, stamnummer: str, serial: str) -> dict:
    resp = client.post(
        "/api/laptops/link",
        json={"stamnummer": stamnummer, "serial_number": serial},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _create_issue(client, serial: str, description: str = "Scherm kapot",
                  reserve_laptop_id: int | None = None) -> dict:
    payload = {
        "serial_number": serial,
        "description": description,
        "reported_date": "2026-04-30",
    }
    if reserve_laptop_id is not None:
        payload["reserve_laptop_id"] = reserve_laptop_id
    resp = client.post("/api/laptop-issues", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _patch_issue(client, issue_id: int, **kwargs) -> dict:
    resp = client.patch(f"/api/laptop-issues/{issue_id}", json=kwargs)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Tests: creating an issue with a reserve laptop ────────────────────────────


def test_create_issue_with_reserve_laptop(client, db_session):
    """Creating an issue with a reserve_laptop_id stores the link and auto-writes a timeline entry."""
    _add_student(db_session, "IS001")
    _link_laptop(client, "IS001", "LAPTOP-IS001")
    reserve = _create_reserve(client, "Reserve-Test", serial="RES-TEST")

    issue = _create_issue(client, "LAPTOP-IS001", reserve_laptop_id=reserve["id"])

    assert issue["reserve_laptop_id"] == reserve["id"]
    assert issue["reserve_laptop_alias"] == "Reserve-Test"
    assert issue["reserve_laptop_serial"] == "RES-TEST"

    # Timeline entry should have been written automatically
    entries_resp = client.get(f"/api/laptop-issues")
    # Verify via detail partial: fetch entries from tracker endpoint
    from app.services.laptop_issue_service import get_entries_for_issue
    from app.db import get_db
    entries = get_entries_for_issue(db_session, issue["id"])
    assert len(entries) == 1
    assert "Reserve-Test" in entries[0]["text"]
    assert "uitgeleend" in entries[0]["text"]


def test_create_issue_with_invalid_reserve_id_returns_422(client, db_session):
    """Using a non-existent reserve_laptop_id must fail with 422."""
    _add_student(db_session, "IS010")
    _link_laptop(client, "IS010", "LAPTOP-IS010")

    resp = client.post("/api/laptop-issues", json={
        "serial_number": "LAPTOP-IS010",
        "description": "Test",
        "reported_date": "2026-04-30",
        "reserve_laptop_id": 99999,
    })

    assert resp.status_code == 422


def test_cannot_use_normal_laptop_as_reserve(client, db_session):
    """Trying to use a non-reserve laptop as a reserve must return 422."""
    _add_student(db_session, "IS020")
    _link_laptop(client, "IS020", "LAPTOP-IS020")
    _add_student(db_session, "IS021")
    normal_laptop = _link_laptop(client, "IS021", "LAPTOP-IS021")

    resp = client.post("/api/laptop-issues", json={
        "serial_number": "LAPTOP-IS020",
        "description": "Test",
        "reported_date": "2026-04-30",
        "reserve_laptop_id": normal_laptop["id"],
    })

    assert resp.status_code == 422


# ── Tests: auto-release on close ─────────────────────────────────────────────


def test_close_issue_releases_reserve_and_writes_entry(client, db_session):
    """Setting status=gesloten must automatically clear reserve_laptop_id and add a timeline entry."""
    _add_student(db_session, "IS030")
    _link_laptop(client, "IS030", "LAPTOP-IS030")
    reserve = _create_reserve(client, "Reserve-Close", serial="RES-CLOSE")

    issue = _create_issue(client, "LAPTOP-IS030", reserve_laptop_id=reserve["id"])
    assert issue["reserve_laptop_id"] == reserve["id"]

    updated = _patch_issue(
        client, issue["id"],
        status="gesloten",
        solution="Scherm vervangen.",
    )

    assert updated["reserve_laptop_id"] is None

    from app.services.laptop_issue_service import get_entries_for_issue
    entries = get_entries_for_issue(db_session, issue["id"])
    texts = [e["text"] for e in entries]
    # Should have: initial "uitgeleend" entry + auto "teruggebracht" entry
    assert any("teruggebracht" in t for t in texts)
    assert any("Reserve-Close" in t for t in texts)


def test_close_issue_without_reserve_does_not_crash(client, db_session):
    """Closing an issue that has no reserve must succeed normally."""
    _add_student(db_session, "IS040")
    _link_laptop(client, "IS040", "LAPTOP-IS040")

    issue = _create_issue(client, "LAPTOP-IS040")
    updated = _patch_issue(client, issue["id"], status="gesloten", solution="Opgelost.")

    assert updated["status"] == "gesloten"
    assert updated["reserve_laptop_id"] is None


# ── Tests: available reserves endpoint ───────────────────────────────────────


def test_reserve_in_use_visible_in_available_list(client, db_session):
    """A reserve laptop linked to an open issue must appear as 'in use' in /available."""
    _add_student(db_session, "IS050")
    _link_laptop(client, "IS050", "LAPTOP-IS050")
    reserve = _create_reserve(client, "Reserve-InUse", serial="RES-INUSE")

    _create_issue(client, "LAPTOP-IS050", reserve_laptop_id=reserve["id"])

    resp = client.get("/api/laptops/reserves/available")
    assert resp.status_code == 200
    options = resp.json()
    match = next((r for r in options if r["id"] == reserve["id"]), None)
    assert match is not None
    assert match["in_use_by_issue_id"] is not None


def test_reserve_available_after_issue_closed(client, db_session):
    """After issue is closed the reserve must appear as available again."""
    _add_student(db_session, "IS060")
    _link_laptop(client, "IS060", "LAPTOP-IS060")
    reserve = _create_reserve(client, "Reserve-Free", serial="RES-FREE")

    issue = _create_issue(client, "LAPTOP-IS060", reserve_laptop_id=reserve["id"])
    _patch_issue(client, issue["id"], status="gesloten", solution="Fixed.")

    resp = client.get("/api/laptops/reserves/available")
    options = resp.json()
    match = next((r for r in options if r["id"] == reserve["id"]), None)
    assert match is not None
    assert match["in_use_by_issue_id"] is None


# ── Tests: updating reserve laptop on an issue ───────────────────────────────


def test_change_reserve_logs_timeline_entry(client, db_session):
    """Swapping the reserve laptop on an existing issue writes a change entry."""
    _add_student(db_session, "IS070")
    _link_laptop(client, "IS070", "LAPTOP-IS070")
    reserve1 = _create_reserve(client, "Reserve-First")
    reserve2 = _create_reserve(client, "Reserve-Second")

    issue = _create_issue(client, "LAPTOP-IS070", reserve_laptop_id=reserve1["id"])

    _patch_issue(client, issue["id"], reserve_laptop_id=reserve2["id"])

    from app.services.laptop_issue_service import get_entries_for_issue
    entries = get_entries_for_issue(db_session, issue["id"])
    texts = [e["text"] for e in entries]
    assert any("Reserve-Second" in t for t in texts)


def test_remove_reserve_logs_terug_entry(client, db_session):
    """Explicitly setting reserve_laptop_id=None (without closing) logs a return entry."""
    _add_student(db_session, "IS080")
    _link_laptop(client, "IS080", "LAPTOP-IS080")
    reserve = _create_reserve(client, "Reserve-Remove")

    issue = _create_issue(client, "LAPTOP-IS080", reserve_laptop_id=reserve["id"])
    updated = _patch_issue(client, issue["id"], reserve_laptop_id=None)

    assert updated["reserve_laptop_id"] is None

    from app.services.laptop_issue_service import get_entries_for_issue
    entries = get_entries_for_issue(db_session, issue["id"])
    texts = [e["text"] for e in entries]
    assert any("teruggebracht" in t for t in texts)
