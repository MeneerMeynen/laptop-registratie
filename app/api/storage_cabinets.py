from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.storage_cabinet import (
    StorageCabinetCreate,
    StorageCabinetDeleteRequest,
    StorageCabinetDeleteResponse,
    StorageCabinetRead,
    StorageCabinetUpdate,
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

router = APIRouter(prefix="/api/storage-cabinets", tags=["storage-cabinets"])


@router.get("", response_model=list[StorageCabinetRead])
def get_cabinets(q: str | None = None, db: Session = Depends(get_db)):
    return list_cabinets(db, q=q)


@router.post("", response_model=StorageCabinetRead)
def create(payload: StorageCabinetCreate, db: Session = Depends(get_db)):
    try:
        cabinet = create_cabinet(db, **payload.model_dump())
    except StorageCabinetValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except StorageCabinetAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return StorageCabinetRead.model_validate(
        {**cabinet.__dict__, "laptop_count": 0}
    )


@router.put("/{cabinet_id}", response_model=StorageCabinetRead)
def update(cabinet_id: int, payload: StorageCabinetUpdate, db: Session = Depends(get_db)):
    update_kwargs = payload.model_dump(exclude_unset=True)
    try:
        cabinet = update_cabinet(db, cabinet_id, **update_kwargs)
    except StorageCabinetValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except StorageCabinetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except StorageCabinetAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    laptop_count = sum(1 for lap in cabinet.laptops if lap.unlinked_at is None)
    return StorageCabinetRead.model_validate(
        {**cabinet.__dict__, "laptop_count": laptop_count}
    )


@router.delete("", response_model=StorageCabinetDeleteResponse)
def delete(payload: StorageCabinetDeleteRequest, db: Session = Depends(get_db)):
    try:
        deleted = delete_cabinets(db, payload.ids)
    except StorageCabinetInUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"deleted": deleted}
