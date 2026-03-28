from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.laptop import Laptop
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
        )
        existing = session.scalars(stmt).first()
        if existing is not None and existing.stamnummer != normalized_stamnummer:
            owner = session.get(Student, existing.stamnummer)
            owner_name = (
                f"{owner.voornaam} {owner.naam}" if owner else existing.stamnummer
            )
            raise LaptopAlreadyLinkedError(
                f"Laptop {normalized_serial} is already linked to {owner_name} ({existing.stamnummer})."
            )

    # 3. Does this student already have an active laptop (other than what we're about to set)?
    active_laptops = [lap for lap in student.laptops if lap.is_active]
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
        .join(Student, Student.stamnummer == Laptop.stamnummer)
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
# Query helper
# ---------------------------------------------------------------------------


def list_students(session: Session) -> list[Student]:
    statement = (
        select(Student)
        .options(selectinload(Student.laptops))
        .order_by(Student.naam, Student.voornaam, Student.stamnummer)
    )
    return list(session.scalars(statement))
