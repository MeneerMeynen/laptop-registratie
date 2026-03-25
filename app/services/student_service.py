from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.student import Student


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
