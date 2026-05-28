import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.laptop import (
    LaptopBulkCreate,
    LaptopBulkResult,
    LaptopCreate,
    LaptopImportResult,
    LaptopLinkRequest,
    LaptopLinkResponse,
    LaptopUpdate,
    ReserveLaptopOption,
)
from app.services.laptop_service import (
    LaptopAlreadyLinkedError,
    LaptopAlreadyUnlinkedError,
    LaptopInCabinetError,
    LaptopNotFoundError,
    LaptopValidationError,
    StudentAlreadyHasLaptopError,
    StudentNotFoundError,
    bulk_create_laptops,
    create_laptop,
    delete_laptop_permanently,
    get_all_laptops,
    import_laptops_csv,
    link_laptop_to_student,
    list_available_reserve_laptops,
    unlink_laptop,
    update_laptop,
)

router = APIRouter(prefix="/api/laptops", tags=["laptops"])


@router.get("", response_model=list[dict])
def list_laptops(
    q: str | None = None,
    active: bool | None = None,
    kind: str = "all",
    db: Session = Depends(get_db),
):
    return get_all_laptops(db, q=q, active=active, kind=kind)


@router.get("/reserves/available", response_model=list[ReserveLaptopOption])
def reserves_available(db: Session = Depends(get_db)):
    return list_available_reserve_laptops(db)


@router.post("", response_model=LaptopLinkResponse)
def create(payload: LaptopCreate, db: Session = Depends(get_db)):
    try:
        laptop = create_laptop(
            db,
            serial_number=payload.serial_number,
            stamnummer=payload.stamnummer,
            is_reserve=payload.is_reserve,
            alias=payload.alias,
            storage_cabinet_id=payload.storage_cabinet_id,
        )
    except LaptopValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except LaptopAlreadyLinkedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return laptop


@router.post("/bulk", response_model=LaptopBulkResult)
def bulk_create(payload: LaptopBulkCreate, db: Session = Depends(get_db)):
    try:
        return bulk_create_laptops(
            db,
            payload.serials,
            is_reserve=payload.is_reserve,
            storage_cabinet_id=payload.storage_cabinet_id,
        )
    except LaptopValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/import", response_model=LaptopImportResult)
async def import_csv(file: UploadFile, db: Session = Depends(get_db)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Alleen CSV-bestanden zijn toegestaan.")
    content = (await file.read()).decode("utf-8-sig")
    result = import_laptops_csv(db, io.StringIO(content))
    return result


@router.put("/{laptop_id}", response_model=LaptopLinkResponse)
def update(laptop_id: int, payload: LaptopUpdate, db: Session = Depends(get_db)):
    update_kwargs = payload.model_dump(exclude_unset=True)
    try:
        laptop = update_laptop(
            db,
            laptop_id=laptop_id,
            **update_kwargs,
        )
    except LaptopValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
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
    except LaptopInCabinetError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
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
