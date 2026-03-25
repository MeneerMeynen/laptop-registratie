from datetime import date
from typing import Optional

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models.laptop import Laptop
from app.models.laptop_issue import LaptopIssue
from app.models.laptop_issue_entry import LaptopIssueEntry
from app.models.student import Student

VALID_STATUSES = ("aangemeld", "open", "gesloten")
VALID_CATEGORIES = ("Scherm", "Toetsenbord", "Software", "Oplader", "Batterij", "Luidspreker", "Overig")


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
        stmt = stmt.where(LaptopIssue.status != "gesloten")

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
            "category": row.LaptopIssue.category,
            "naam": row.naam,
            "voornaam": row.voornaam,
            "stamnummer": row.stamnummer,
        }
        for row in rows
    ]


def create_issue(
    db: Session,
    serial_number: str,
    description: str,
    reported_date: date,
    category: Optional[str] = None,
) -> LaptopIssue:
    issue = LaptopIssue(
        serial_number=serial_number.strip(),
        description=description.strip(),
        reported_date=reported_date,
        status="open",
        category=category or None,
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


def list_laptops_with_issues(db: Session, search: str = "") -> list[dict]:
    """All laptops that have at least one issue, with student info and status counts."""
    counts = (
        select(
            LaptopIssue.serial_number.label("serial_number"),
            func.count(case((LaptopIssue.status == "open", 1))).label("open_count"),
            func.count(case((LaptopIssue.status == "gesloten", 1))).label("gesloten_count"),
            func.count(case((LaptopIssue.status == "aangemeld", 1))).label("aangemeld_count"),
        )
        .group_by(LaptopIssue.serial_number)
        .subquery()
    )

    stmt = (
        select(
            counts.c.serial_number,
            counts.c.open_count,
            counts.c.gesloten_count,
            counts.c.aangemeld_count,
            Student.naam,
            Student.voornaam,
            Student.klas,
        )
        .outerjoin(Laptop, Laptop.serial_number == counts.c.serial_number)
        .outerjoin(Student, Student.stamnummer == Laptop.stamnummer)
        .order_by(counts.c.open_count.desc(), counts.c.serial_number)
    )

    if search:
        q = f"%{search}%"
        stmt = stmt.where(
            or_(
                counts.c.serial_number.ilike(q),
                Student.naam.ilike(q),
                Student.voornaam.ilike(q),
            )
        )

    rows = db.execute(stmt).all()
    return [
        {
            "serial_number": row.serial_number,
            "open_count": int(row.open_count),
            "gesloten_count": int(row.gesloten_count),
            "aangemeld_count": int(row.aangemeld_count),
            "naam": row.naam,
            "voornaam": row.voornaam,
            "klas": row.klas,
        }
        for row in rows
    ]


def get_entries_for_issue(db: Session, issue_id: int) -> list[dict]:
    """All follow-up entries for an issue, oldest first."""
    entries = db.execute(
        select(LaptopIssueEntry)
        .where(LaptopIssueEntry.issue_id == issue_id)
        .order_by(LaptopIssueEntry.created_at.asc())
    ).scalars().all()
    return [{"id": e.id, "text": e.text, "created_at": e.created_at} for e in entries]


def add_issue_entry(db: Session, issue_id: int, text: str) -> LaptopIssueEntry:
    """Add a timestamped follow-up entry to an issue."""
    entry = LaptopIssueEntry(issue_id=issue_id, text=text.strip())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_issues_for_serial(db: Session, serial: str) -> list[dict]:
    """All issues for a specific laptop serial number, newest first, with entries.
    Uses a single extra query for entries instead of N+1 per issue.
    """
    issues = db.execute(
        select(LaptopIssue)
        .where(LaptopIssue.serial_number == serial)
        .order_by(LaptopIssue.reported_date.desc(), LaptopIssue.id.desc())
    ).scalars().all()

    if not issues:
        return []

    # Fetch all entries for these issues in one query
    issue_ids = [i.id for i in issues]
    all_entries = db.execute(
        select(LaptopIssueEntry)
        .where(LaptopIssueEntry.issue_id.in_(issue_ids))
        .order_by(LaptopIssueEntry.created_at.asc())
    ).scalars().all()

    entries_map: dict[int, list] = {i.id: [] for i in issues}
    for e in all_entries:
        entries_map[e.issue_id].append(
            {"id": e.id, "text": e.text, "created_at": e.created_at}
        )

    return [
        {
            "id": i.id,
            "serial_number": i.serial_number,
            "description": i.description,
            "reported_date": i.reported_date,
            "status": i.status,
            "solution": i.solution,
            "category": i.category,
            "entries": entries_map[i.id],
        }
        for i in issues
    ]


def get_student_for_serial(db: Session, serial: str) -> dict | None:
    """Return the student linked to a laptop serial number, or None."""
    row = db.execute(
        select(Student.naam, Student.voornaam, Student.klas, Student.stamnummer)
        .join(Laptop, Laptop.stamnummer == Student.stamnummer)
        .where(Laptop.serial_number == serial)
    ).first()
    if not row:
        return None
    return {
        "naam": row.naam,
        "voornaam": row.voornaam,
        "klas": row.klas,
        "stamnummer": row.stamnummer,
    }


def get_global_stats(db: Session) -> dict:
    """Total aangemeld / open / gesloten counts across all laptops."""
    row = db.execute(
        select(
            func.count(case((LaptopIssue.status == "aangemeld", 1))).label("aangemeld"),
            func.count(case((LaptopIssue.status == "open", 1))).label("open"),
            func.count(case((LaptopIssue.status == "gesloten", 1))).label("gesloten"),
        )
    ).first()
    return {
        "aangemeld": int(row.aangemeld),
        "open": int(row.open),
        "gesloten": int(row.gesloten),
    }


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
