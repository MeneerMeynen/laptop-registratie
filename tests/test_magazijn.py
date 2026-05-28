"""Tests for the magazijn (warehouse) storage location: a StorageCabinet with
kind="magazijn" whose laptops CAN be assigned to a student (unlike kind="kast")."""

import pytest

from app.models.laptop import Laptop
from app.models.student import Student
from app.services.laptop_service import (
    LaptopInCabinetError,
    bulk_create_laptops,
    get_all_laptops,
    link_laptop_to_student,
)
from app.services.storage_cabinet_service import (
    StorageCabinetInUseError,
    StorageCabinetValidationError,
    create_cabinet,
    delete_cabinets,
    list_cabinets,
)


# ── Service-layer: create / list ──────────────────────────────────────────────

def test_create_magazijn(db_session):
    mag = create_cabinet(db_session, name="Magazijn ICT", kind="magazijn")
    assert mag.kind == "magazijn"


def test_create_cabinet_defaults_to_kast(db_session):
    cab = create_cabinet(db_session, name="Kast 1")
    assert cab.kind == "kast"


def test_create_cabinet_rejects_invalid_kind(db_session):
    with pytest.raises(StorageCabinetValidationError):
        create_cabinet(db_session, name="Bad", kind="garage")


def test_list_cabinets_filtered_by_kind(db_session):
    create_cabinet(db_session, name="Kast A", kind="kast")
    create_cabinet(db_session, name="Magazijn B", kind="magazijn")

    kasten = list_cabinets(db_session, kind="kast")
    magazijnen = list_cabinets(db_session, kind="magazijn")

    assert [c["name"] for c in kasten] == ["Kast A"]
    assert [c["name"] for c in magazijnen] == ["Magazijn B"]
    assert magazijnen[0]["kind"] == "magazijn"


# ── Bulk add ──────────────────────────────────────────────────────────────────

def test_bulk_add_laptops_to_magazijn(db_session):
    mag = create_cabinet(db_session, name="Magazijn Bulk", kind="magazijn")
    result = bulk_create_laptops(
        db_session, ["SN-M1", "SN-M2"], storage_cabinet_id=mag.id
    )
    assert result == {"created": 2, "skipped": 0, "errors": []}
    laps = db_session.query(Laptop).filter(Laptop.storage_cabinet_id == mag.id).all()
    assert {lap.serial_number for lap in laps} == {"SN-M1", "SN-M2"}


# ── Kernfunctionaliteit: koppelen vanuit magazijn ─────────────────────────────

def test_link_laptop_from_magazijn_succeeds(db_session):
    """A magazijn laptop can be assigned to a student and leaves the magazijn."""
    mag = create_cabinet(db_session, name="Magazijn Q", kind="magazijn")
    db_session.add(Laptop(serial_number="SN-MQ1", storage_cabinet_id=mag.id))
    db_session.add(Student(stamnummer="S001", naam="Test", voornaam="Leerling"))
    db_session.commit()

    laptop = link_laptop_to_student(
        db_session, stamnummer="S001", serial_number="SN-MQ1"
    )

    assert laptop.stamnummer == "S001"
    assert laptop.storage_cabinet_id is None
    assert laptop.linked_at is not None

    # Exactly one active record for the serial — no duplicate created.
    active = (
        db_session.query(Laptop)
        .filter(Laptop.serial_number == "SN-MQ1", Laptop.unlinked_at.is_(None))
        .all()
    )
    assert len(active) == 1
    assert active[0].id == laptop.id


def test_link_laptop_from_kast_still_blocked(db_session):
    """Regression: a kast laptop remains non-assignable."""
    kast = create_cabinet(db_session, name="Kast Q", kind="kast")
    db_session.add(Laptop(serial_number="SN-KQ1", storage_cabinet_id=kast.id))
    db_session.add(Student(stamnummer="S002", naam="Test", voornaam="Leerling"))
    db_session.commit()

    with pytest.raises(LaptopInCabinetError):
        link_laptop_to_student(db_session, stamnummer="S002", serial_number="SN-KQ1")


def test_get_all_laptops_kind_magazijn_vs_cabinet(db_session):
    kast = create_cabinet(db_session, name="Kast F", kind="kast")
    mag = create_cabinet(db_session, name="Magazijn F", kind="magazijn")
    db_session.add(Laptop(serial_number="SN-K", storage_cabinet_id=kast.id))
    db_session.add(Laptop(serial_number="SN-M", storage_cabinet_id=mag.id))
    db_session.commit()

    cabinet_laptops = get_all_laptops(db_session, kind="cabinet")
    magazijn_laptops = get_all_laptops(db_session, kind="magazijn")

    assert [l["serial_number"] for l in cabinet_laptops] == ["SN-K"]
    assert [l["serial_number"] for l in magazijn_laptops] == ["SN-M"]


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_magazijn_refuses_when_in_use(db_session):
    mag = create_cabinet(db_session, name="Magazijn X", kind="magazijn")
    db_session.add(Laptop(serial_number="SN-MX", storage_cabinet_id=mag.id))
    db_session.commit()

    with pytest.raises(StorageCabinetInUseError):
        delete_cabinets(db_session, [mag.id])


# ── HTTP routes ───────────────────────────────────────────────────────────────

def test_create_magazijn_route(client):
    resp = client.post(
        "/api/storage-cabinets",
        json={"name": "API Magazijn", "kind": "magazijn"},
    )
    assert resp.status_code == 200
    assert resp.json()["kind"] == "magazijn"


def test_list_route_filtered_by_kind(client):
    client.post("/api/storage-cabinets", json={"name": "K1", "kind": "kast"})
    client.post("/api/storage-cabinets", json={"name": "M1", "kind": "magazijn"})

    kasten = client.get("/api/storage-cabinets?kind=kast").json()
    magazijnen = client.get("/api/storage-cabinets?kind=magazijn").json()

    assert [c["name"] for c in kasten] == ["K1"]
    assert [c["name"] for c in magazijnen] == ["M1"]


def test_link_endpoint_accepts_magazijn_laptop(client, db_session):
    mag_resp = client.post(
        "/api/storage-cabinets", json={"name": "Link Magazijn", "kind": "magazijn"}
    )
    mag_id = mag_resp.json()["id"]
    client.post(
        "/api/laptops",
        json={"serial_number": "SN-LINK-M", "storage_cabinet_id": mag_id},
    )
    db_session.add(Student(stamnummer="L200", naam="X", voornaam="Y"))
    db_session.commit()

    resp = client.post(
        "/api/laptops/link",
        json={"stamnummer": "L200", "serial_number": "SN-LINK-M"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["stamnummer"] == "L200"
    assert data["storage_cabinet_id"] is None


def test_ui_magazijn_manage_partial(client):
    client.post(
        "/api/storage-cabinets", json={"name": "UI-Magazijn", "kind": "magazijn"}
    )
    resp = client.get("/ui/storage-cabinets/manage?kind=magazijn")
    assert resp.status_code == 200
    assert "UI-Magazijn" in resp.text


def test_ui_laptops_manage_kind_magazijn_filters_and_badges(client):
    """The laptop list filtered to kind=magazijn shows only magazijn laptops,
    each with a 'Magazijn' badge — and excludes kast laptops."""
    mag_id = client.post(
        "/api/storage-cabinets", json={"name": "Mag-Filter", "kind": "magazijn"}
    ).json()["id"]
    kast_id = client.post(
        "/api/storage-cabinets", json={"name": "Kast-Filter", "kind": "kast"}
    ).json()["id"]
    client.post(
        "/api/laptops", json={"serial_number": "MAG-FX", "storage_cabinet_id": mag_id}
    )
    client.post(
        "/api/laptops", json={"serial_number": "KAST-FX", "storage_cabinet_id": kast_id}
    )

    resp = client.get("/ui/laptops/manage?kind=magazijn")
    assert resp.status_code == 200
    assert "MAG-FX" in resp.text
    assert "KAST-FX" not in resp.text
    assert ">Magazijn<" in resp.text
