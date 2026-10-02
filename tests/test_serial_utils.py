"""Scanned Lenovo codes (QR URL / long barcode) are reduced to the bare serial."""
import base64

import pytest

from app.models.laptop import Laptop
from app.models.student import Student
from app.services import photo_service
from app.services.serial_utils import normalize_serial

QR = "https://support.lenovo.com/qrcode?sn=PW0P8KG5&mtm=21MVS04B00"
LONG = "pW0P8KG5PW90B6321007"


@pytest.mark.parametrize("raw, expected", [
    (QR, "PW0P8KG5"),
    (LONG, "PW0P8KG5"),
    ("PW0P8KG5PW90B6321007", "PW0P8KG5"),
    ("https://support.lenovo.com/qrcode?SN=PW0P8KG5", "PW0P8KG5"),
    ("  PW0P8KG5 ", "PW0P8KG5"),
    ("abc123", "ABC123"),
    # Other 20-character codes (e.g. a Dell PPID) are left whole.
    ("CN0ABCDE1234567890AB", "CN0ABCDE1234567890AB"),
    ("", ""),
    (None, ""),
])
def test_normalize_serial(raw, expected):
    assert normalize_serial(raw) == expected


def _student(session, stamnummer: str) -> None:
    session.add(Student(stamnummer=stamnummer, naam="Peeters", voornaam="Lien", klas="5B"))
    session.commit()


def test_link_with_qr_code_stores_serial(client, db_session):
    _student(db_session, "SER1")
    resp = client.post("/api/laptops/link", json={"stamnummer": "SER1", "serial_number": QR})
    assert resp.status_code == 200, resp.text
    assert resp.json()["serial_number"] == "PW0P8KG5"


def test_qr_and_long_barcode_are_the_same_laptop(client, db_session):
    _student(db_session, "SER2")
    _student(db_session, "SER3")
    assert client.post("/api/laptops/link",
                       json={"stamnummer": "SER2", "serial_number": QR}).status_code == 200
    # Same laptop scanned via the other barcode → recognised as already linked.
    resp = client.post("/api/laptops/link", json={"stamnummer": "SER3", "serial_number": LONG})
    assert resp.status_code != 200
    assert db_session.query(Laptop).filter(Laptop.serial_number == "PW0P8KG5").count() == 1


def test_eigen_laptop_scan_still_works(client, db_session):
    _student(db_session, "SER4")
    resp = client.post("/api/laptops/link",
                       json={"stamnummer": "SER4", "serial_number": "eigen laptop"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["eigen_laptop"] is True


def test_defect_with_long_barcode(client):
    resp = client.post("/api/laptop-issues", json={
        "serial_number": LONG, "description": "Scherm flikkert", "reported_date": "2026-10-02",
    })
    assert resp.status_code == 201, resp.text
    assert resp.json()["serial_number"] == "PW0P8KG5"


def test_report_lookup_with_qr_code(client):
    resp = client.get("/api/laptops/report", params={"serial": QR})
    assert resp.status_code == 200
    assert resp.json()["serial"] == "PW0P8KG5"


def test_photo_upload_with_qr_code(client, tmp_path, monkeypatch):
    monkeypatch.setattr(photo_service, "UPLOAD_DIR", tmp_path)
    jpeg = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"
    resp = client.post("/api/photos/base64", json={
        "serial_number": QR, "image_data": base64.b64encode(jpeg).decode(),
    })
    assert resp.status_code in (200, 201), resp.text
    assert (tmp_path / "PW0P8KG5").is_dir()


def test_bulk_add_with_lenovo_codes(client):
    resp = client.post("/api/laptops/bulk",
                       json={"serials": [QR, "PF5ABCDE1234567890XY"], "is_reserve": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 2
