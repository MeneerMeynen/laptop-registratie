"""Tests for bulk laptop creation (reserve pool and storage cabinets)."""

import pytest

from app.models.laptop import Laptop
from app.services.laptop_service import (
    LaptopValidationError,
    bulk_create_laptops,
)
from app.services.storage_cabinet_service import create_cabinet


# ── Reserve ───────────────────────────────────────────────────────────────────

def test_bulk_reserve_generates_aliases(db_session):
    result = bulk_create_laptops(
        db_session, ["SN-R1", "SN-R2", "SN-R3"], is_reserve=True
    )
    assert result == {"created": 3, "skipped": 0, "errors": []}

    reserves = db_session.query(Laptop).filter(Laptop.is_reserve.is_(True)).all()
    aliases = sorted(lap.alias for lap in reserves)
    assert aliases == ["Reserve-1", "Reserve-2", "Reserve-3"]
    assert all(lap.linked_at is None for lap in reserves)


def test_bulk_reserve_alias_continues_numbering(db_session):
    db_session.add(Laptop(serial_number="SN-OLD", is_reserve=True, alias="Reserve-2"))
    db_session.commit()

    bulk_create_laptops(db_session, ["SN-NEW1", "SN-NEW2"], is_reserve=True)

    aliases = sorted(
        lap.alias
        for lap in db_session.query(Laptop).filter(Laptop.is_reserve.is_(True))
    )
    assert aliases == ["Reserve-2", "Reserve-3", "Reserve-4"]


def test_bulk_reserve_skips_existing_serial(db_session):
    db_session.add(Laptop(serial_number="SN-DUP", is_reserve=True, alias="Reserve-1"))
    db_session.commit()

    result = bulk_create_laptops(db_session, ["SN-DUP", "SN-FRESH"], is_reserve=True)
    assert result["created"] == 1
    assert result["skipped"] == 1


# ── Cabinet ─────────────────────────────────────────────────────────────────

def test_bulk_cabinet_adds_laptops(db_session):
    cab = create_cabinet(db_session, name="Bulk-Kast")
    result = bulk_create_laptops(
        db_session, ["SN-C1", "SN-C2"], storage_cabinet_id=cab.id
    )
    assert result == {"created": 2, "skipped": 0, "errors": []}
    laps = db_session.query(Laptop).filter(Laptop.storage_cabinet_id == cab.id).all()
    assert {lap.serial_number for lap in laps} == {"SN-C1", "SN-C2"}
    assert all(lap.is_reserve is False and lap.linked_at is not None for lap in laps)


def test_bulk_cabinet_skips_active_serial(db_session):
    cab = create_cabinet(db_session, name="Kast-Skip")
    db_session.add(Laptop(serial_number="SN-ACTIVE", linked_at=None))
    # an actively-linked non-reserve laptop
    db_session.add(Laptop(serial_number="SN-LINKED", storage_cabinet_id=cab.id))
    db_session.commit()

    result = bulk_create_laptops(
        db_session, ["SN-LINKED", "SN-OK"], storage_cabinet_id=cab.id
    )
    assert result["created"] == 1
    assert result["skipped"] == 1


def test_bulk_cabinet_unknown_cabinet_raises(db_session):
    with pytest.raises(LaptopValidationError):
        bulk_create_laptops(db_session, ["SN-X"], storage_cabinet_id=9999)


# ── Input handling ─────────────────────────────────────────────────────────

def test_bulk_dedupes_input(db_session):
    result = bulk_create_laptops(
        db_session, ["SN-A", "SN-A", " SN-A ", "SN-B"], is_reserve=True
    )
    assert result["created"] == 2
    assert result["skipped"] == 2


def test_bulk_invalid_serial_collected_as_error(db_session):
    result = bulk_create_laptops(
        db_session, ["SN-OK", "bad serial!", ""], is_reserve=True
    )
    assert result["created"] == 1
    assert len(result["errors"]) == 1
    assert "bad serial!" in result["errors"][0]


def test_bulk_requires_a_target(db_session):
    with pytest.raises(LaptopValidationError):
        bulk_create_laptops(db_session, ["SN-A"])


# ── HTTP route ───────────────────────────────────────────────────────────────

def test_bulk_route_reserve(client):
    resp = client.post(
        "/api/laptops/bulk",
        json={"serials": ["SN-RT1", "SN-RT2"], "is_reserve": True},
    )
    assert resp.status_code == 200
    assert resp.json() == {"created": 2, "skipped": 0, "errors": []}


def test_bulk_route_cabinet(client):
    cab_id = client.post("/api/storage-cabinets", json={"name": "RT-Kast"}).json()["id"]
    resp = client.post(
        "/api/laptops/bulk",
        json={"serials": ["SN-RTC1"], "storage_cabinet_id": cab_id},
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 1


def test_bulk_route_unknown_cabinet_returns_422(client):
    resp = client.post(
        "/api/laptops/bulk",
        json={"serials": ["SN-Z"], "storage_cabinet_id": 9999},
    )
    assert resp.status_code == 422
