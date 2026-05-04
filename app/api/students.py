import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.student import (
    StudentCreate,
    StudentDeleteRequest,
    StudentDeleteResponse,
    StudentRead,
    StudentUpdate,
)
from app.services.laptop_service import list_students
from app.services.student_import import import_students_from_stream
from app.services.student_service import (
    StudentAlreadyExistsError,
    StudentNotFoundError,
    StudentValidationError,
    create_student,
    delete_students_by_stamnummers,
    update_student,
)

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("", response_model=list[StudentRead])
def get_students(db: Session = Depends(get_db)):
    return list_students(db)


@router.post("/import")
def import_students(file: UploadFile, db: Session = Depends(get_db)):
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")
    content = file.file.read().decode("utf-8-sig")
    count = import_students_from_stream(db, io.StringIO(content))
    return {"imported": count}


@router.post("", response_model=StudentRead)
def create(payload: StudentCreate, db: Session = Depends(get_db)):
    try:
        student = create_student(db, **payload.model_dump())
    except StudentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except StudentAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return student


@router.put("/{stamnummer}", response_model=StudentRead)
def update(stamnummer: str, payload: StudentUpdate, db: Session = Depends(get_db)):
    try:
        student = update_student(db, stamnummer, **payload.model_dump())
    except StudentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return student


@router.delete("", response_model=StudentDeleteResponse)
def delete_students(payload: StudentDeleteRequest, db: Session = Depends(get_db)):
    deleted = delete_students_by_stamnummers(db, payload.stamnummers)
    return {"deleted": deleted}
