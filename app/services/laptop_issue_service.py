from datetime import date
from typing import Optional

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.laptop import Laptop
from app.models.laptop_issue import LaptopIssue
from app.models.laptop_issue_entry import LaptopIssueEntry
from app.models.student import Student

VALID_STATUSES = ("aangemeld", "open", "gesloten")
VALID_CATEGORIES = (
    "Scherm",
    "Toetsenbord",
    "Software",
    "Oplader",
    "Batterij",
    "Luidspreker",
    "Accessoires",
    "Overig",
)


class IssueValidationError(ValueError):
    pass


def _student_label(naam: str | None, voornaam: str | None) -> str:
    parts = " ".join(filter(None, [voornaam, naam])).strip()
    return parts or "onbekende leerling"


def _reserve_label(laptop: Laptop) -> str:
    if laptop.alias and laptop.serial_number:
        return f"{laptop.alias} ({laptop.serial_number})"
    return laptop.alias or laptop.serial_number or f"#{laptop.id}"


def _validate_reserve_laptop(db: Session, reserve_laptop_id: int) -> Laptop:
    laptop = db.get(Laptop, reserve_laptop_id)
    if laptop is None:
        raise IssueValidationError("Reserve-laptop niet gevonden.")
    if not laptop.is_reserve:
        raise IssueValidationError("Geselecteerde laptop is geen reserve-laptop.")
    return laptop


def list_issues(db: Session, search: str = "", include_closed: bool = False) -> list[dict]:
    reserve = aliased(Laptop)
    stmt = (
        select(
            LaptopIssue,
            Student.naam,
            Student.voornaam,
            Student.stamnummer,
            reserve.alias.label("reserve_alias"),
            reserve.serial_number.label("reserve_serial"),
        )
        .outerjoin(
            Laptop,
            and_(Laptop.serial_number == LaptopIssue.serial_number, Laptop.unlinked_at.is_(None)),
        )
        .outerjoin(Student, Student.stamnummer == Laptop.stamnummer)
        .outerjoin(reserve, reserve.id == LaptopIssue.reserve_laptop_id)
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
            "reserve_laptop_id": row.LaptopIssue.reserve_laptop_id,
            "reserve_laptop_alias": row.reserve_alias,
            "reserve_laptop_serial": row.reserve_serial,
        }
        for row in rows
    ]


def create_issue(
    db: Session,
    serial_number: str,
    description: str,
    reported_date: date,
    category: Optional[str] = None,
    reserve_laptop_id: Optional[int] = None,
) -> LaptopIssue:
    reserve_laptop: Laptop | None = None
    if reserve_laptop_id is not None:
        reserve_laptop = _validate_reserve_laptop(db, reserve_laptop_id)

    issue = LaptopIssue(
        serial_number=serial_number.strip(),
        description=description.strip(),
        reported_date=reported_date,
        status="aangemeld",
        category=category or None,
        reserve_laptop_id=reserve_laptop.id if reserve_laptop else None,
    )
    db.add(issue)
    db.flush()  # populate issue.id without committing

    if reserve_laptop is not None:
        student = _student_for_issue(db, issue)
        student_label = _student_label(
            student.get("naam") if student else None,
            student.get("voornaam") if student else None,
        )
        db.add(
            LaptopIssueEntry(
                issue_id=issue.id,
                text=f"Reserve-laptop {_reserve_label(reserve_laptop)} uitgeleend aan {student_label}.",
            )
        )

    db.commit()
    db.refresh(issue)
    return issue


def _student_for_issue(db: Session, issue: LaptopIssue) -> dict | None:
    return get_student_for_serial(db, issue.serial_number)


def update_issue(db: Session, issue_id: int, data: dict) -> Optional[LaptopIssue]:
    issue = db.get(LaptopIssue, issue_id)
    if not issue:
        return None

    old_status = issue.status
    old_reserve_id = issue.reserve_laptop_id
    reserve_changed = "reserve_laptop_id" in data
    new_reserve_id = data.get("reserve_laptop_id") if reserve_changed else old_reserve_id

    if reserve_changed and new_reserve_id is not None:
        _validate_reserve_laptop(db, new_reserve_id)

    for key, value in data.items():
        setattr(issue, key, value)

    new_status = issue.status
    auto_released_reserve_id: int | None = None
    if (
        new_status == "gesloten"
        and old_status != "gesloten"
        and issue.reserve_laptop_id is not None
    ):
        auto_released_reserve_id = issue.reserve_laptop_id
        issue.reserve_laptop_id = None

    # Build timeline entries before committing so the whole change is atomic.
    final_reserve_id = issue.reserve_laptop_id
    entry_texts: list[str] = []
    if auto_released_reserve_id is not None:
        laptop = db.get(Laptop, auto_released_reserve_id)
        if laptop is not None:
            entry_texts.append(
                f"Reserve-laptop {_reserve_label(laptop)} teruggebracht (issue gesloten)."
            )
    elif reserve_changed and old_reserve_id != final_reserve_id:
        student = _student_for_issue(db, issue)
        student_label = _student_label(
            student.get("naam") if student else None,
            student.get("voornaam") if student else None,
        )
        if final_reserve_id is None and old_reserve_id is not None:
            old_laptop = db.get(Laptop, old_reserve_id)
            if old_laptop is not None:
                entry_texts.append(
                    f"Reserve-laptop {_reserve_label(old_laptop)} teruggebracht."
                )
        elif final_reserve_id is not None:
            new_laptop = db.get(Laptop, final_reserve_id)
            if new_laptop is not None:
                if old_reserve_id is None:
                    entry_texts.append(
                        f"Reserve-laptop {_reserve_label(new_laptop)} uitgeleend aan {student_label}."
                    )
                else:
                    old_laptop = db.get(Laptop, old_reserve_id)
                    old_label = _reserve_label(old_laptop) if old_laptop else f"#{old_reserve_id}"
                    entry_texts.append(
                        f"Reserve-laptop gewijzigd: {old_label} → {_reserve_label(new_laptop)}."
                    )

    for entry_text in entry_texts:
        db.add(LaptopIssueEntry(issue_id=issue.id, text=entry_text.strip()))

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


def list_laptops_with_issues(
    db: Session,
    search: str = "",
    statuses: list[str] | None = None,
) -> list[dict]:
    """All laptops that have at least one issue matching the given statuses."""
    if statuses is None:
        statuses = ["aangemeld", "open"]

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
        .outerjoin(
            Laptop,
            and_(Laptop.serial_number == counts.c.serial_number, Laptop.unlinked_at.is_(None)),
        )
        .outerjoin(Student, Student.stamnummer == Laptop.stamnummer)
        .order_by(counts.c.open_count.desc(), counts.c.serial_number)
    )

    status_col_map = {
        "aangemeld": counts.c.aangemeld_count,
        "open": counts.c.open_count,
        "gesloten": counts.c.gesloten_count,
    }
    status_conditions = [status_col_map[s] > 0 for s in statuses if s in status_col_map]

    if status_conditions:
        stmt = stmt.where(or_(*status_conditions))
    else:
        return []  # nothing selected → empty list

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


def update_entry(db: Session, entry_id: int, text: str) -> Optional[LaptopIssueEntry]:
    """Update the text of an entry."""
    entry = db.get(LaptopIssueEntry, entry_id)
    if not entry:
        return None
    entry.text = text.strip()
    db.commit()
    db.refresh(entry)
    return entry


def delete_entry(db: Session, entry_id: int) -> Optional[int]:
    """Delete an entry and return its issue_id, or None if not found."""
    entry = db.get(LaptopIssueEntry, entry_id)
    if not entry:
        return None
    issue_id = entry.issue_id
    db.delete(entry)
    db.commit()
    return issue_id


def get_issues_for_serial(db: Session, serial: str) -> list[dict]:
    """All issues for a specific laptop serial number, newest first, with entries.
    Uses a single extra query for entries instead of N+1 per issue.
    """
    reserve = aliased(Laptop)
    rows = db.execute(
        select(
            LaptopIssue,
            reserve.alias.label("reserve_alias"),
            reserve.serial_number.label("reserve_serial"),
        )
        .outerjoin(reserve, reserve.id == LaptopIssue.reserve_laptop_id)
        .where(LaptopIssue.serial_number == serial)
        .order_by(LaptopIssue.reported_date.desc(), LaptopIssue.id.desc())
    ).all()

    if not rows:
        return []

    issues = [row.LaptopIssue for row in rows]

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
            "id": row.LaptopIssue.id,
            "serial_number": row.LaptopIssue.serial_number,
            "description": row.LaptopIssue.description,
            "reported_date": row.LaptopIssue.reported_date,
            "status": row.LaptopIssue.status,
            "solution": row.LaptopIssue.solution,
            "category": row.LaptopIssue.category,
            "reserve_laptop_id": row.LaptopIssue.reserve_laptop_id,
            "reserve_laptop_alias": row.reserve_alias,
            "reserve_laptop_serial": row.reserve_serial,
            "entries": entries_map[row.LaptopIssue.id],
        }
        for row in rows
    ]


def get_student_for_serial(db: Session, serial: str) -> dict | None:
    """Return the student linked to a laptop serial number, or None."""
    row = db.execute(
        select(Student.naam, Student.voornaam, Student.klas, Student.stamnummer, Laptop.linked_at)
        .join(Laptop, and_(Laptop.stamnummer == Student.stamnummer, Laptop.unlinked_at.is_(None)))
        .where(Laptop.serial_number == serial)
    ).first()
    if not row:
        return None
    return {
        "naam": row.naam,
        "voornaam": row.voornaam,
        "klas": row.klas,
        "stamnummer": row.stamnummer,
        "linked_at": row.linked_at,
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


def get_laptop_type(db: Session, serial: str) -> str | None:
    """Return 'reserve' or 'uitleen' for special laptop types, None for regular."""
    row = db.execute(
        select(Laptop.is_reserve, Laptop.storage_cabinet_id)
        .where(Laptop.serial_number == serial)
        .order_by(Laptop.unlinked_at.is_(None).desc(), Laptop.id.desc())
        .limit(1)
    ).first()
    if not row:
        return None
    if row.is_reserve:
        return "reserve"
    if row.storage_cabinet_id is not None:
        return "uitleen"
    return None


def search_laptops_for_autocomplete(db: Session, q: str) -> list[dict]:
    """Return laptops matching serial number or student name for autocomplete."""
    pattern = f"%{q}%"
    rows = db.execute(
        select(Laptop.serial_number, Student.naam, Student.voornaam, Student.stamnummer)
        .outerjoin(Student, Student.stamnummer == Laptop.stamnummer)
        .where(Laptop.serial_number.isnot(None))
        .where(Laptop.unlinked_at.is_(None))
        .where(Laptop.is_reserve.is_(False))
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
