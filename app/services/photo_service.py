"""Service layer for laptop photo management."""
import os
import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.laptop_photo import LaptopPhoto

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads" / "laptops"


def _ensure_dir(serial_number: str) -> Path:
    """Create and return the upload directory for a given serial."""
    target = UPLOAD_DIR / serial_number
    target.mkdir(parents=True, exist_ok=True)
    return target


def save_photo(db: Session, serial_number: str, file_bytes: bytes, extension: str = ".jpg") -> LaptopPhoto:
    """Save a photo to disk and record it in the database."""
    target_dir = _ensure_dir(serial_number)
    filename = f"{uuid.uuid4().hex}{extension}"
    filepath = target_dir / filename

    with open(filepath, "wb") as f:
        f.write(file_bytes)

    photo = LaptopPhoto(serial_number=serial_number, filename=filename)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


def list_photos(db: Session, serial_number: str) -> list[dict]:
    """Return all photos for a given serial number."""
    photos = (
        db.query(LaptopPhoto)
        .filter(LaptopPhoto.serial_number == serial_number)
        .order_by(LaptopPhoto.created_at.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "serial_number": p.serial_number,
            "filename": p.filename,
            "url": f"/uploads/laptops/{p.serial_number}/{p.filename}",
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in photos
    ]


def delete_photo(db: Session, photo_id: int) -> bool:
    """Delete a photo from disk and database. Returns True if found."""
    photo = db.query(LaptopPhoto).filter(LaptopPhoto.id == photo_id).first()
    if not photo:
        return False

    # Remove file from disk
    filepath = UPLOAD_DIR / photo.serial_number / photo.filename
    if filepath.exists():
        filepath.unlink()

    db.delete(photo)
    db.commit()
    return True


def delete_all_photos_for_serial(db: Session, serial_number: str) -> int:
    """Delete all photos for a serial. Returns count deleted."""
    photos = db.query(LaptopPhoto).filter(LaptopPhoto.serial_number == serial_number).all()
    count = len(photos)

    # Remove directory from disk
    target_dir = UPLOAD_DIR / serial_number
    if target_dir.exists():
        shutil.rmtree(target_dir)

    for p in photos:
        db.delete(p)
    db.commit()
    return count
