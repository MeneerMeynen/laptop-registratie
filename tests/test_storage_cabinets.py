"""Tests for the storage_cabinets feature: service, API, and laptop integration."""

import pytest

from app.models.laptop import Laptop
from app.models.storage_cabinet import StorageCabinet
from app.models.student import Student
from app.services.laptop_service import (
    LaptopInCabinetError,
    LaptopValidationError,
    create_laptop,
    link_laptop_to_student,
)
from app.services.storage_cabinet_service import (
    StorageCabinetAlreadyExistsError,
    StorageCabinetInUseError,
    StorageCabinetNotFoundError,
    StorageCabinetValidationError,
    create_cabinet,
    delete_cabinets,
    list_cabinets,
    update_cabinet,
)


# ── Service-layer tests ───────────────────────────────────────────────────────

def test_create_cabinet_minimal(db_session):
    cab = create_cabinet(db_session, name="Kast B201")
    assert cab.id is not None
    assert cab.name == "Kast B201"
    assert cab.location is None
    assert cab.capacity is None


def test_create_cabinet_full(db_session):
    cab = create_cabinet(
        db_session,
        name="Kast 1",
        location="A101",
        description="Voor 2e jaar",
        capacity=8,
    )
    assert cab.location == "A101"
    assert cab.description == "Voor 2e jaar"
    assert cab.capacity == 8


def test_create_cabinet_requires_name(db_session):
    with pytest.raises(StorageCabinetValidationError):
        create_cabinet(db_session, name="   ")


def test_create_cabinet_unique_name(db_session):
    create_cabinet(db_session, name="Kast 1")
    with pytest.raises(StorageCabinetAlreadyExistsError):
        create_cabinet(db_session, name="Kast 1")


def test_update_cabinet(db_session):
    cab = create_cabinet(db_session, name="Kast 1", location="A101")
    updated = update_cabinet(db_session, cab.id, location="B202", capacity=12)
    assert updated.location == "B202"
    assert updated.capacity == 12
    assert updated.name == "Kast 1"  # unchanged


def test_update_cabinet_not_found(db_session):
    with pytest.raises(StorageCabinetNotFoundError):
        update_cabinet(db_session, 9999, name="x")


def test_list_cabinets_with_laptop_count(db_session):
    cab = create_cabinet(db_session, name="Kast A", capacity=4)
    create_cabinet(db_session, name="Kast B")
    # Add a laptop to Kast A
    db_session.add(Laptop(serial_number="SN-CAB-1", storage_cabinet_id=cab.id))
    db_session.commit()

    results = list_cabinets(db_session)
    by_name = {r["name"]: r for r in results}
    assert by_name["Kast A"]["laptop_count"] == 1
    assert by_name["Kast B"]["laptop_count"] == 0


def test_delete_cabinet_refuses_when_in_use(db_session):
    cab = create_cabinet(db_session, name="Kast X")
    db_session.add(Laptop(serial_number="SN-CAB-X", storage_cabinet_id=cab.id))
    db_session.commit()

    with pytest.raises(StorageCabinetInUseError):
        delete_cabinets(db_session, [cab.id])


def test_delete_empty_cabinet(db_session):
    cab = create_cabinet(db_session, name="Empty")
    deleted = delete_cabinets(db_session, [cab.id])
    assert deleted == 1
    assert db_session.query(StorageCabinet).count() == 0


# ── Laptop service integration ────────────────────────────────────────────────

def test_create_cabinet_laptop(db_session):
    cab = create_cabinet(db_session, name="Kast Y")
    lap = create_laptop(
        db_session,
        serial_number="SN-CAB-Y1",
        storage_cabinet_id=cab.id,
    )
    assert lap.storage_cabinet_id == cab.id
    assert lap.stamnummer is None
    assert lap.is_reserve is False


def test_create_cabinet_laptop_requires_serial(db_session):
    cab = create_cabinet(db_session, name="Kast Z")
    with pytest.raises(LaptopValidationError):
        create_laptop(db_session, storage_cabinet_id=cab.id)


def test_create_cabinet_laptop_rejects_unknown_cabinet(db_session):
    with pytest.raises(LaptopValidationError):
        create_laptop(db_session, serial_number="SN-XYZ", storage_cabinet_id=999)


def test_link_laptop_refuses_cabinet_laptop(db_session):
    """A laptop sitting in a cabinet cannot be linked to a student."""
    cab = create_cabinet(db_session, name="Kast Q")
    db_session.add(Laptop(serial_number="SN-Q1", storage_cabinet_id=cab.id))
    db_session.add(Student(stamnummer="S001", naam="Test", voornaam="Leerling"))
    db_session.commit()

    with pytest.raises(LaptopInCabinetError):
        link_laptop_to_student(db_session, stamnummer="S001", serial_number="SN-Q1")


# ── HTTP route tests ──────────────────────────────────────────────────────────

def test_create_cabinet_route(client):
    resp = client.post(
        "/api/storage-cabinets",
        json={"name": "Kast 1", "location": "A101", "capacity": 8},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Kast 1"
    assert data["location"] == "A101"
    assert data["capacity"] == 8
    assert data["laptop_count"] == 0


def test_create_cabinet_conflict(client):
    client.post("/api/storage-cabinets", json={"name": "Dup"})
    resp = client.post("/api/storage-cabinets", json={"name": "Dup"})
    assert resp.status_code == 409


def test_list_cabinets_route(client):
    client.post("/api/storage-cabinets", json={"name": "Alpha"})
    client.post("/api/storage-cabinets", json={"name": "Beta"})
    resp = client.get("/api/storage-cabinets")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Alpha" in names
    assert "Beta" in names


def test_update_cabinet_route(client):
    create = client.post(
        "/api/storage-cabinets",
        json={"name": "Edit", "location": "Old"},
    )
    cab_id = create.json()["id"]
    resp = client.put(
        f"/api/storage-cabinets/{cab_id}",
        json={"location": "New", "capacity": 10},
    )
    assert resp.status_code == 200
    assert resp.json()["location"] == "New"
    assert resp.json()["capacity"] == 10


def test_delete_cabinet_route(client, db_session):
    create = client.post("/api/storage-cabinets", json={"name": "ToDelete"})
    cab_id = create.json()["id"]
    resp = client.request(
        "DELETE",
        "/api/storage-cabinets",
        json={"ids": [cab_id]},
    )
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 1


def test_delete_cabinet_in_use_returns_409(client, db_session):
    create = client.post("/api/storage-cabinets", json={"name": "InUse"})
    cab_id = create.json()["id"]
    db_session.add(Laptop(serial_number="SN-USE", storage_cabinet_id=cab_id))
    db_session.commit()

    resp = client.request(
        "DELETE",
        "/api/storage-cabinets",
        json={"ids": [cab_id]},
    )
    assert resp.status_code == 409


def test_create_cabinet_laptop_via_api(client):
    cab_resp = client.post("/api/storage-cabinets", json={"name": "API-Kast"})
    cab_id = cab_resp.json()["id"]
    resp = client.post(
        "/api/laptops",
        json={"serial_number": "SN-API-CAB", "storage_cabinet_id": cab_id},
    )
    assert resp.status_code == 200
    assert resp.json()["storage_cabinet_id"] == cab_id
    assert resp.json()["stamnummer"] is None


def test_link_endpoint_rejects_cabinet_laptop(client, db_session):
    cab_resp = client.post("/api/storage-cabinets", json={"name": "Block-Kast"})
    cab_id = cab_resp.json()["id"]
    client.post(
        "/api/laptops",
        json={"serial_number": "SN-BLOCK", "storage_cabinet_id": cab_id},
    )
    db_session.add(Student(stamnummer="L100", naam="X", voornaam="Y"))
    db_session.commit()

    resp = client.post(
        "/api/laptops/link",
        json={"stamnummer": "L100", "serial_number": "SN-BLOCK"},
    )
    assert resp.status_code == 409
    assert "uitleenkast" in resp.json()["detail"].lower()


def test_ui_cabinets_manage_partial(client):
    client.post("/api/storage-cabinets", json={"name": "UI-Kast", "location": "Z9"})
    resp = client.get("/ui/storage-cabinets/manage")
    assert resp.status_code == 200
    assert "UI-Kast" in resp.text
    assert "Z9" in resp.text


def test_ui_laptops_manage_with_kind_cabinet(client, db_session):
    cab_resp = client.post("/api/storage-cabinets", json={"name": "Filter-Kast"})
    cab_id = cab_resp.json()["id"]
    client.post(
        "/api/laptops",
        json={"serial_number": "SN-FILT", "storage_cabinet_id": cab_id},
    )

    resp = client.get("/ui/laptops/manage?kind=cabinet")
    assert resp.status_code == 200
    assert "SN-FILT" in resp.text
    assert "Filter-Kast" in resp.text
