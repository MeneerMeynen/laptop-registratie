"""API routes for laptop photo management."""
import base64

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.photo_service import delete_photo, list_photos, save_photo

router = APIRouter(prefix="/api/photos", tags=["photos"])


class PhotoBase64Request(BaseModel):
    serial_number: str
    image_data: str  # base64 encoded JPEG


@router.get("/{serial_number}")
def get_photos(serial_number: str, db: Session = Depends(get_db)):
    """List all photos for a laptop serial number."""
    return list_photos(db, serial_number)


@router.post("", status_code=201)
def upload_photo(file: UploadFile, serial_number: str, db: Session = Depends(get_db)):
    """Upload a photo file for a laptop."""
    if not serial_number.strip():
        raise HTTPException(status_code=400, detail="Serienummer is verplicht.")

    content = file.file.read()
    ext = ".jpg"
    if file.filename:
        parts = file.filename.rsplit(".", 1)
        if len(parts) == 2:
            ext = f".{parts[1].lower()}"

    photo = save_photo(db, serial_number.strip(), content, ext)
    return {
        "id": photo.id,
        "serial_number": photo.serial_number,
        "filename": photo.filename,
        "url": f"/uploads/laptops/{photo.serial_number}/{photo.filename}",
    }


@router.post("/base64", status_code=201)
def upload_photo_base64(req: PhotoBase64Request, db: Session = Depends(get_db)):
    """Upload a base64-encoded photo (from webcam capture)."""
    if not req.serial_number.strip():
        raise HTTPException(status_code=400, detail="Serienummer is verplicht.")

    # Strip data URL prefix if present (e.g. "data:image/jpeg;base64,")
    image_data = req.image_data
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]

    try:
        file_bytes = base64.b64decode(image_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Ongeldige base64 data.")

    photo = save_photo(db, req.serial_number.strip(), file_bytes, ".jpg")
    return {
        "id": photo.id,
        "serial_number": photo.serial_number,
        "filename": photo.filename,
        "url": f"/uploads/laptops/{photo.serial_number}/{photo.filename}",
    }


@router.delete("/{photo_id}", status_code=204)
def remove_photo(photo_id: int, db: Session = Depends(get_db)):
    """Delete a single photo."""
    if not delete_photo(db, photo_id):
        raise HTTPException(status_code=404, detail="Foto niet gevonden.")
