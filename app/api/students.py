import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.student import StudentDeleteRequest, StudentDeleteResponse, StudentRead
from app.services.laptop_service import list_students
from app.services.student_import import import_students_from_stream
from app.services.student_service import delete_students_by_stamnummers

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


@router.delete("", response_model=StudentDeleteResponse)
def delete_students(payload: StudentDeleteRequest, db: Session = Depends(get_db)):
    deleted = delete_students_by_stamnummers(db, payload.stamnummers)
    return {"deleted": deleted}
