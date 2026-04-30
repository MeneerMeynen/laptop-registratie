import csv
from datetime import datetime
from typing import TextIO

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.laptop import Laptop
from app.models.laptop_issue import LaptopIssue
from app.models.student import Student


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class StudentNotFoundError(ValueError):
    pass


class LaptopAlreadyLinkedError(ValueError):
    pass


class StudentAlreadyHasLaptopError(ValueError):
    def __init__(self, stamnummer: str, existing_serials: list[str]):
        self.stamnummer = stamnummer
        self.existing_serials = existing_serials
        serials = ", ".join(existing_serials)
        super().__init__(f"Student {stamnummer} already has laptop(s): {serials}.")


class LaptopValidationError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EIGEN_LAPTOP_TRIGGER = "eigen laptop"


def is_eigen_laptop_scan(serial: str) -> bool:
    return serial.strip().lower() == _EIGEN_LAPTOP_TRIGGER


def display_serial(laptop: Laptop) -> str:
    """Return the serial number as shown in the UI (empty for eigen laptop)."""
    if laptop.eigen_laptop:
        return ""
    return laptop.serial_number or ""


def describe_serial(laptop: Laptop) -> str:
    """Return a human-readable description (used in error messages)."""
    if laptop.eigen_laptop:
        return "eigen laptop"
    if laptop.is_reserve:
        return f"reserve-laptop '{laptop.alias or laptop.serial_number or ''}'"
    return laptop.serial_number or ""


# ---------------------------------------------------------------------------
# Core service function
# ---------------------------------------------------------------------------


def link_laptop_to_student(
    session: Session,
    stamnummer: str,
    serial_number: str,
    overwrite_existing: bool = False,
) -> Laptop:
    """Link a laptop (or eigen laptop) to a student.

    When ``serial_number`` is "eigen laptop" (case-insensitive):
    - ``eigen_laptop`` is set to True
    - ``serial_number`` is stored as NULL in the database

    Raises:
        StudentNotFoundError: if the student does not exist.
        LaptopAlreadyLinkedError: if the serial is already linked to another student.
        StudentAlreadyHasLaptopError: if the student already has a laptop and
            ``overwrite_existing`` is False.
    """
    normalized_stamnummer = stamnummer.strip()
    normalized_serial = serial_number.strip()
    is_own = is_eigen_laptop_scan(normalized_serial)

    # 1. Student must exist.
    student = session.get(Student, normalized_stamnummer, options=[selectinload(Student.laptops)])
    if student is None:
        raise StudentNotFoundError(f"Student {normalized_stamnummer} does not exist.")

    # 2. For regular serials: check if that serial is already actively linked to *someone else*.
    if not is_own:
        stmt = select(Laptop).where(
            Laptop.serial_number == normalized_serial,
            Laptop.unlinked_at.is_(None),
            Laptop.is_reserve.is_(False),
        )
        existing = session.scalars(stmt).first()
        if existing is not None and existing.stamnummer != normalized_stamnummer:
            owner = session.get(Student, existing.stamnummer) if existing.stamnummer else None
            owner_name = (
                f"{owner.voornaam} {owner.naam}" if owner else (existing.stamnummer or "?")
            )
            raise LaptopAlreadyLinkedError(
                f"Laptop {normalized_serial} is already linked to {owner_name} ({existing.stamnummer})."
            )

    # 3. Does this student already have an active (non-reserve) laptop other than this one?
    active_laptops = [lap for lap in student.laptops if lap.is_active and not lap.is_reserve]
    other_laptops = [
        lap for lap in active_laptops
        if not (is_own and lap.eigen_laptop)  # skip if same eigen_laptop slot
        and not (not is_own and lap.serial_number == normalized_serial)  # skip if same serial
    ]
    if other_laptops and not overwrite_existing:
        raise StudentAlreadyHasLaptopError(
            stamnummer=normalized_stamnummer,
            existing_serials=[describe_serial(lap) for lap in other_laptops],
        )

    # 4. Unlink existing active laptops if overwriting.
    for lap in active_laptops:
        lap.unlinked_at = datetime.now()
    session.flush()

    # 5. Create the new laptop record.
    laptop = Laptop(
        serial_number=None if is_own else normalized_serial,
        stamnummer=normalized_stamnummer,
        eigen_laptop=is_own,
        linked_at=datetime.now(),
    )
    session.add(laptop)
    session.commit()
    session.refresh(laptop)
    return laptop


class LaptopNotFoundError(ValueError):
    pass


class LaptopAlreadyUnlinkedError(ValueError):
    pass


def unlink_laptop(session: Session, laptop_id: int) -> Laptop:
    """Mark a laptop assignment as returned (ingeleverd)."""
    laptop = session.get(Laptop, laptop_id)
    if laptop is None:
        raise LaptopNotFoundError("Laptop niet gevonden.")
    if laptop.unlinked_at is not None:
        raise LaptopAlreadyUnlinkedError("Laptop is al ingeleverd.")
    laptop.unlinked_at = datetime.now()
    session.commit()
    session.refresh(laptop)
    return laptop


def get_assignment_history(session: Session, serial_number: str) -> list[dict]:
    """All assignments (active + historical) for a serial, newest first."""
    stmt = (
        select(Laptop, Student.naam, Student.voornaam, Student.klas)
        .outerjoin(Student, Student.stamnummer == Laptop.stamnummer)
        .where(Laptop.serial_number == serial_number)
        .order_by(Laptop.linked_at.desc())
    )
    rows = session.execute(stmt).all()
    return [
        {
            "id": row.Laptop.id,
            "stamnummer": row.Laptop.stamnummer,
            "naam": row.naam,
            "voornaam": row.voornaam,
            "klas": row.klas,
            "linked_at": row.Laptop.linked_at,
            "unlinked_at": row.Laptop.unlinked_at,
            "is_active": row.Laptop.is_active,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Laptop management (CRUD)
# ---------------------------------------------------------------------------


class LaptopDeleteError(ValueError):
    pass


def get_all_laptops(
    session: Session,
    q: str | None = None,
    active: bool | None = None,
    kind: str = "all",
) -> list[dict]:
    """Return all laptop records with joined student info, optionally filtered.

    ``kind`` can be ``"all"`` (default), ``"normal"`` (excludes reserve), or
    ``"reserve"`` (only reserve laptops).
    """
    stmt = (
        select(Laptop, Student.naam, Student.voornaam, Student.klas)
        .outerjoin(Student, Student.stamnummer == Laptop.stamnummer)
        # MariaDB does not support NULLS LAST syntax — use ISNULL to sort NULLs last.
        .order_by(func.isnull(Laptop.linked_at).asc(), Laptop.linked_at.desc(), Laptop.id.desc())
    )

    if kind == "reserve":
        stmt = stmt.where(Laptop.is_reserve.is_(True))
    elif kind == "normal":
        stmt = stmt.where(Laptop.is_reserve.is_(False))

    rows = session.execute(stmt).all()
    results = []
    for row in rows:
        if active is not None and row.Laptop.is_active != active:
            continue
        serial = row.Laptop.serial_number or ""
        if q:
            q_lower = q.lower()
            searchable = (
                f"{serial} {row.Laptop.stamnummer or ''} {row.Laptop.alias or ''} "
                f"{row.naam or ''} {row.voornaam or ''} {row.klas or ''}"
            ).lower()
            if q_lower not in searchable:
                continue
        results.append({
            "id": row.Laptop.id,
            "serial_number": serial,
            "stamnummer": row.Laptop.stamnummer,
            "eigen_laptop": row.Laptop.eigen_laptop,
            "is_reserve": row.Laptop.is_reserve,
            "alias": row.Laptop.alias,
            "linked_at": row.Laptop.linked_at,
            "unlinked_at": row.Laptop.unlinked_at,
            "is_active": row.Laptop.is_active,
            "naam": row.naam,
            "voornaam": row.voornaam,
            "klas": row.klas,
        })
    return results


def create_laptop(
    session: Session,
    serial_number: str | None = None,
    stamnummer: str | None = None,
    *,
    is_reserve: bool = False,
    alias: str | None = None,
) -> Laptop:
    """Create a new laptop record.

    For a regular laptop: ``stamnummer`` is required and ``serial_number`` is required.
    For a reserve laptop: ``alias`` is required; ``stamnummer`` must be empty.
    """
    normalized_serial = (serial_number or "").strip() or None
    normalized_stamnummer = (stamnummer or "").strip() or None
    normalized_alias = (alias or "").strip() or None

    if is_reserve:
        if normalized_stamnummer:
            raise LaptopValidationError(
                "Een reserve-laptop mag niet aan een leerling gekoppeld zijn."
            )
        if not normalized_alias:
            raise LaptopValidationError("Reserve-laptop vereist een alias.")
    else:
        if not normalized_stamnummer:
            raise LaptopValidationError("Stamnummer is verplicht voor een gewone laptop.")
        if not normalized_serial:
            raise LaptopValidationError("Serienummer is verplicht voor een gewone laptop.")
        student = session.get(Student, normalized_stamnummer)
        if student is None:
            raise StudentNotFoundError(f"Student {normalized_stamnummer} bestaat niet.")

    if normalized_serial:
        existing = session.scalars(
            select(Laptop).where(
                Laptop.serial_number == normalized_serial,
                Laptop.unlinked_at.is_(None),
                Laptop.is_reserve.is_(False),
            )
        ).first()
        if existing is not None and not is_reserve:
            raise LaptopAlreadyLinkedError(
                f"Serienummer {normalized_serial} is al actief gekoppeld."
            )

    laptop = Laptop(
        serial_number=normalized_serial,
        stamnummer=None if is_reserve else normalized_stamnummer,
        eigen_laptop=False,
        is_reserve=is_reserve,
        alias=normalized_alias,
        linked_at=None if is_reserve else datetime.now(),
    )
    session.add(laptop)
    session.commit()
    session.refresh(laptop)
    return laptop


def update_laptop(
    session: Session,
    laptop_id: int,
    serial_number: str | None = None,
    stamnummer: str | None = None,
    is_reserve: bool | None = None,
    alias: str | None = None,
) -> Laptop:
    """Update fields of a laptop record."""
    laptop = session.get(Laptop, laptop_id)
    if laptop is None:
        raise LaptopNotFoundError("Laptop niet gevonden.")

    if is_reserve is not None and is_reserve != laptop.is_reserve:
        if is_reserve:
            laptop.is_reserve = True
            laptop.stamnummer = None
            if laptop.unlinked_at is None and laptop.linked_at is not None:
                laptop.unlinked_at = datetime.now()
        else:
            laptop.is_reserve = False

    if alias is not None:
        normalized = alias.strip()
        laptop.alias = normalized or None

    if stamnummer is not None and not laptop.is_reserve:
        normalized = stamnummer.strip()
        if not normalized:
            raise LaptopValidationError("Stamnummer mag niet leeg zijn voor een gewone laptop.")
        if session.get(Student, normalized) is None:
            raise StudentNotFoundError(f"Student {normalized} bestaat niet.")
        laptop.stamnummer = normalized

    if serial_number is not None:
        normalized = serial_number.strip() or None
        if normalized:
            conflict = session.scalars(
                select(Laptop).where(
                    Laptop.serial_number == normalized,
                    Laptop.unlinked_at.is_(None),
                    Laptop.is_reserve.is_(False),
                    Laptop.id != laptop_id,
                )
            ).first()
            if conflict is not None and not laptop.is_reserve:
                raise LaptopAlreadyLinkedError(
                    f"Serienummer {normalized} is al actief gekoppeld aan een andere leerling."
                )
        laptop.serial_number = normalized

    if laptop.is_reserve and not laptop.alias:
        raise LaptopValidationError("Reserve-laptop vereist een alias.")

    session.commit()
    session.refresh(laptop)
    return laptop


def delete_laptop_permanently(session: Session, laptop_id: int) -> None:
    """Hard-delete a laptop record from the database."""
    laptop = session.get(Laptop, laptop_id)
    if laptop is None:
        raise LaptopNotFoundError("Laptop niet gevonden.")
    session.delete(laptop)
    session.commit()


def import_laptops_csv(session: Session, stream: TextIO) -> dict:
    """Bulk-import laptops from a CSV stream (serial_number,stamnummer).

    For each row:
    - If the serial is already actively linked to the same student → skip (counted as updated).
    - If the serial is new or was previously unlinked → create a new record.
    - Errors (unknown student, missing fields) are collected without stopping the import.

    Returns a dict with keys: created, updated, errors.
    """
    created = 0
    updated = 0
    errors: list[str] = []

    reader = csv.DictReader(stream)
    for i, row in enumerate(reader, start=2):
        serial = (row.get("serial_number") or row.get("Serienummer") or "").strip()
        stamnummer = (row.get("stamnummer") or row.get("Stamnummer") or "").strip()

        if not serial or not stamnummer:
            errors.append(f"Rij {i}: serial_number en stamnummer zijn verplicht.")
            continue

        student = session.get(Student, stamnummer)
        if student is None:
            errors.append(f"Rij {i}: student {stamnummer} niet gevonden.")
            continue

        active = session.scalars(
            select(Laptop).where(
                Laptop.serial_number == serial,
                Laptop.unlinked_at.is_(None),
                Laptop.is_reserve.is_(False),
            )
        ).first()

        if active is not None and active.stamnummer == stamnummer:
            updated += 1
            continue

        if active is not None:
            active.unlinked_at = datetime.now()

        session.add(Laptop(
            serial_number=serial,
            stamnummer=stamnummer,
            eigen_laptop=False,
            linked_at=datetime.now(),
        ))
        created += 1

    session.commit()
    return {"created": created, "updated": updated, "errors": errors}


# ---------------------------------------------------------------------------
# Reserve-laptop helpers
# ---------------------------------------------------------------------------


def list_available_reserve_laptops(session: Session) -> list[dict]:
    """All reserve laptops with info about whether they are currently in use.

    A reserve laptop is "in use" when it is referenced by an issue whose
    status is not ``gesloten``.
    """
    in_use_subq = (
        select(
            LaptopIssue.reserve_laptop_id.label("laptop_id"),
            LaptopIssue.id.label("issue_id"),
            LaptopIssue.serial_number.label("issue_serial"),
        )
        .where(
            LaptopIssue.reserve_laptop_id.isnot(None),
            LaptopIssue.status != "gesloten",
        )
        .subquery()
    )

    student_alias = (
        select(
            Laptop.serial_number.label("serial_number"),
            Student.naam.label("naam"),
            Student.voornaam.label("voornaam"),
        )
        .outerjoin(Student, Student.stamnummer == Laptop.stamnummer)
        .where(Laptop.unlinked_at.is_(None))
        .subquery()
    )

    stmt = (
        select(
            Laptop,
            in_use_subq.c.issue_id,
            in_use_subq.c.issue_serial,
            student_alias.c.naam,
            student_alias.c.voornaam,
        )
        .outerjoin(in_use_subq, in_use_subq.c.laptop_id == Laptop.id)
        .outerjoin(
            student_alias,
            student_alias.c.serial_number == in_use_subq.c.issue_serial,
        )
        .where(Laptop.is_reserve.is_(True))
        # MariaDB does not support NULLS LAST — use ISNULL workaround.
        .order_by(func.isnull(Laptop.alias).asc(), Laptop.alias.asc(), Laptop.id.asc())
    )
    rows = session.execute(stmt).all()
    results = []
    for row in rows:
        in_use_by = None
        if row.issue_id is not None:
            naam_parts = " ".join(filter(None, [row.voornaam, row.naam])).strip()
            in_use_by = naam_parts or row.issue_serial or "?"
        results.append({
            "id": row.Laptop.id,
            "alias": row.Laptop.alias,
            "serial_number": row.Laptop.serial_number,
            "in_use_by_issue_id": row.issue_id,
            "in_use_by_student": in_use_by,
        })
    return results


# ---------------------------------------------------------------------------
# Query helper
# ---------------------------------------------------------------------------


def list_students(session: Session) -> list[Student]:
    statement = (
        select(Student)
        .options(selectinload(Student.laptops))
        .order_by(Student.naam, Student.voornaam, Student.stamnummer)
    )
    return list(session.scalars(statement))
