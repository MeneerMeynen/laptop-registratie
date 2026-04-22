import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.laptop import (
    LaptopCreate,
    LaptopImportResult,
    LaptopLinkRequest,
    LaptopLinkResponse,
    LaptopUpdate,
)
from app.services.laptop_service import (
    LaptopAlreadyLinkedError,
    LaptopAlreadyUnlinkedError,
    LaptopNotFoundError,
    StudentNotFoundError,
    StudentAlreadyHasLaptopError,
    create_laptop,
    delete_laptop_permanently,
    get_all_laptops,
    import_laptops_csv,
    link_laptop_to_student,
    unlink_laptop,
    update_laptop,
)

router = APIRouter(prefix="/api/laptops", tags=["laptops"])


@router.get("", response_model=list[dict])
def list_laptops(
    q: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
):
    return get_all_laptops(db, q=q, active=active)


@router.post("", response_model=LaptopLinkResponse)
def create(payload: LaptopCreate, db: Session = Depends(get_db)):
    try:
        laptop = create_laptop(db, serial_number=payload.serial_number, stamnummer=payload.stamnummer)
    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LaptopAlreadyLinkedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return laptop


@router.post("/import", response_model=LaptopImportResult)
async def import_csv(file: UploadFile, db: Session = Depends(get_db)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Alleen CSV-bestanden zijn toegestaan.")
    content = (await file.read()).decode("utf-8-sig")
    result = import_laptops_csv(db, io.StringIO(content))
    return result


@router.put("/{laptop_id}", response_model=LaptopLinkResponse)
def update(laptop_id: int, payload: LaptopUpdate, db: Session = Depends(get_db)):
    try:
        laptop = update_laptop(
            db,
            laptop_id=laptop_id,
            serial_number=payload.serial_number,
            stamnummer=payload.stamnummer,
        )
    except LaptopNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LaptopAlreadyLinkedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return laptop


@router.delete("/{laptop_id}", status_code=204)
def delete_permanently(laptop_id: int, db: Session = Depends(get_db)):
    try:
        delete_laptop_permanently(db, laptop_id)
    except LaptopNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/link", response_model=LaptopLinkResponse)
def link_laptop(payload: LaptopLinkRequest, db: Session = Depends(get_db)):
    try:
        laptop = link_laptop_to_student(
            session=db,
            stamnummer=payload.stamnummer,
            serial_number=payload.serial_number,
            overwrite_existing=payload.overwrite_existing,
        )
    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LaptopAlreadyLinkedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except StudentAlreadyHasLaptopError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "stamnummer": exc.stamnummer,
                "existing_serials": exc.existing_serials,
                "requires_confirmation": True,
            },
        )
    return laptop


@router.post("/{laptop_id}/unlink", response_model=LaptopLinkResponse)
def unlink(laptop_id: int, db: Session = Depends(get_db)):
    try:
        laptop = unlink_laptop(session=db, laptop_id=laptop_id)
    except LaptopNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LaptopAlreadyUnlinkedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return laptop
