"""Validation tests for photo_service.

These tests don't touch the DB — they exercise the input-validation guards
that protect against path traversal and bad uploads.
"""
import pytest

from app.services.photo_service import (
    MAX_PHOTO_BYTES,
    PhotoValidationError,
    _safe_extension,
    _safe_serial,
    save_photo,
)


@pytest.mark.parametrize(
    "serial",
    [
        "../../etc/passwd",
        "../escape",
        "with/slash",
        "with\\backslash",
        "spaces not allowed",
        "",
        "a" * 101,
        "weird;chars",
    ],
)
def test_safe_serial_rejects_bad_inputs(serial):
    with pytest.raises(PhotoValidationError):
        _safe_serial(serial)


@pytest.mark.parametrize("serial", ["ABC123", "abc-123", "abc_123", "ABC.123", "a", "A" * 100])
def test_safe_serial_accepts_normal_barcodes(serial):
    assert _safe_serial(serial) == serial


@pytest.mark.parametrize("ext", [".php", ".html", ".svg", ".exe", "", ".", "jpg"])
def test_safe_extension_rejects_dangerous(ext):
    with pytest.raises(PhotoValidationError):
        _safe_extension(ext)


@pytest.mark.parametrize("ext", [".jpg", ".jpeg", ".png", ".webp", ".JPG", ".PNG"])
def test_safe_extension_accepts_image(ext):
    assert _safe_extension(ext) in {".jpg", ".jpeg", ".png", ".webp"}


def test_save_photo_rejects_traversal_serial(db_session):
    with pytest.raises(PhotoValidationError):
        save_photo(db_session, "../evil", b"data", ".jpg")


def test_save_photo_rejects_oversize(db_session):
    with pytest.raises(PhotoValidationError):
        save_photo(db_session, "ABC123", b"x" * (MAX_PHOTO_BYTES + 1), ".jpg")


def test_save_photo_rejects_empty(db_session):
    with pytest.raises(PhotoValidationError):
        save_photo(db_session, "ABC123", b"", ".jpg")
