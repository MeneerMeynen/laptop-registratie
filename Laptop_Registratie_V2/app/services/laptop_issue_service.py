from datetime import date
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.laptop import Laptop
from app.models.laptop_issue import LaptopIssue
from app.models.student import Student


def list_issues(db: Session, search: str = "", include_closed: bool = False) -> list[dict]:
    stmt = (
        select(
            LaptopIssue,
            Student.naam,
            Student.voornaam,
            Student.stamnummer,
        )
        .outerjoin(Laptop, Laptop.serial_number == LaptopIssue.serial_number)
        .outerjoin(Student, Student.stamnummer == Laptop.stamnummer)
        .order_by(LaptopIssue.reported_date.desc(), LaptopIssue.id.desc())
    )

    if not include_closed:
        stmt = stmt.where(LaptopIssue.status == "open")

    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                LaptopIssue.serial_number.ilike(q),
                Student.naam.ilike(q),
                Student.voornaam.ilike(q),
            )
        )

    rows = db.execute(stmt).all()
    return [
        {
            "id": row.LaptopIssue.id,
            "serial_number": row.LaptopIssue.serial_number,
            "description": row.LaptopIssue.description,
            "reported_date": row.LaptopIssue.reported_date,
            "status": row.LaptopIssue.status,
            "solution": row.LaptopIssue.solution,
            "naam": row.naam,
            "voornaam": row.voornaam,
            "stamnummer": row.stamnummer,
        }
        for row in rows
    ]


def create_issue(
    db: Session, serial_number: str, description: str, reported_date: date
) -> LaptopIssue:
    issue = LaptopIssue(
        serial_number=serial_number.strip(),
        description=description.strip(),
        reported_date=reported_date,
        status="open",
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


def update_issue(db: Session, issue_id: int, data: dict) -> Optional[LaptopIssue]:
    issue = db.get(LaptopIssue, issue_id)
    if not issue:
        return None
    for key, value in data.items():
        setattr(issue, key, value)
    db.commit()
    db.refresh(issue)
    return issue


def delete_issue(db: Session, issue_id: int) -> bool:
    issue = db.get(LaptopIssue, issue_id)
    if not issue:
        return False
    db.delete(issue)
    db.commit()
    return True


def search_laptops_for_autocomplete(db: Session, q: str) -> list[dict]:
    """Return laptops matching serial number or student name for autocomplete."""
    pattern = f"%{q}%"
    rows = db.execute(
        select(Laptop.serial_number, Student.naam, Student.voornaam, Student.stamnummer)
        .outerjoin(Student, Student.stamnummer == Laptop.stamnummer)
        .where(Laptop.serial_number.isnot(None))
        .where(
            or_(
                Laptop.serial_number.ilike(pattern),
                Student.naam.ilike(pattern),
                Student.voornaam.ilike(pattern),
            )
        )
        .limit(20)
    ).all()
    return [
        {
            "serial_number": row.serial_number,
            "naam": row.naam,
            "voornaam": row.voornaam,
            "stamnummer": row.stamnummer,
        }
        for row in rows
    ]
