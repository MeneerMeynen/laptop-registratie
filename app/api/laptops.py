from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.laptop import LaptopLinkRequest, LaptopLinkResponse
from app.services.laptop_service import (
    LaptopAlreadyLinkedError,
    LaptopAlreadyUnlinkedError,
    LaptopNotFoundError,
    StudentAlreadyHasLaptopError,
    StudentNotFoundError,
    link_laptop_to_student,
    unlink_laptop,
)

router = APIRouter(prefix="/api/laptops", tags=["laptops"])


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
