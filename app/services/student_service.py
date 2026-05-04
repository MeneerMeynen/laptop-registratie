from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.student import Student


class StudentValidationError(ValueError):
    pass


class StudentNotFoundError(ValueError):
    pass


class StudentAlreadyExistsError(ValueError):
    pass


_EDITABLE_FIELDS = (
    "instellingsnummer",
    "naam",
    "voornaam",
    "klas",
    "klascode",
    "klasnummer",
    "gebruikersnaam",
    "pointer",
)


def delete_students_by_stamnummers(session: Session, stamnummers: list[str]) -> int:
    """Delete students (and their laptops via cascade) by stamnummer list."""
    normalized = [s.strip() for s in stamnummers if s.strip()]
    if not normalized:
        return 0

    stmt = select(Student).where(Student.stamnummer.in_(normalized))
    students = list(session.scalars(stmt))

    for student in students:
        session.delete(student)

    session.commit()
    return len(students)


def create_student(session: Session, *, stamnummer: str, **fields) -> Student:
    """Create a single student manually."""
    normalized = (stamnummer or "").strip()
    if not normalized:
        raise StudentValidationError("Stamnummer is verplicht.")

    if session.get(Student, normalized) is not None:
        raise StudentAlreadyExistsError(f"Student {normalized} bestaat al.")

    student = Student(stamnummer=normalized, last_import=datetime.now(timezone.utc))
    for key in _EDITABLE_FIELDS:
        value = fields.get(key)
        if value is not None:
            setattr(student, key, value.strip() or None)

    session.add(student)
    session.commit()
    session.refresh(student)
    return student


def update_student(session: Session, stamnummer: str, **fields) -> Student:
    """Update editable fields of a student. Stamnummer (PK) cannot change."""
    student = session.get(Student, stamnummer)
    if student is None:
        raise StudentNotFoundError(f"Student {stamnummer} bestaat niet.")

    for key in _EDITABLE_FIELDS:
        if key in fields and fields[key] is not None:
            value = fields[key].strip()
            setattr(student, key, value or None)

    session.commit()
    session.refresh(student)
    return student
