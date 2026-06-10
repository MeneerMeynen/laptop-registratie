import csv
import re
from datetime import date, datetime
from typing import TextIO

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.laptop import Laptop
from app.models.laptop_issue import LaptopIssue
from app.models.storage_cabinet import StorageCabinet
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

# Serienummers komen van barcode-scans: alfanumeriek plus enkele scheidingstekens.
_SERIAL_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_RESERVE_ALIAS_RE = re.compile(r"^Reserve-(\d+)$")


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


class LaptopInCabinetError(ValueError):
    """Raised when trying to link a cabinet-laptop to a student."""
    pass


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

    # 2. For regular serials: check if that serial is already actively linked to *someone else*,
    #    or sits in a storage location (kast or magazijn).
    from_magazijn: Laptop | None = None
    if not is_own:
        stmt = select(Laptop).where(
            Laptop.serial_number == normalized_serial,
            Laptop.unlinked_at.is_(None),
            Laptop.is_reserve.is_(False),
        )
        existing = session.scalars(stmt).first()
        if existing is not None and existing.storage_cabinet_id is not None:
            cabinet = session.get(StorageCabinet, existing.storage_cabinet_id)
            if cabinet is not None and cabinet.kind == "magazijn":
                # Een magazijn-laptop mag toegekend worden: hij verlaat het magazijn.
                from_magazijn = existing
            else:
                cabinet_label = cabinet.name if cabinet else f"#{existing.storage_cabinet_id}"
                raise LaptopInCabinetError(
                    f"Laptop {normalized_serial} staat in uitleenkast '{cabinet_label}' "
                    f"en kan niet aan een leerling gekoppeld worden."
                )
        if existing is not None and from_magazijn is None and existing.stamnummer != normalized_stamnummer:
            owner = session.get(Student, existing.stamnummer) if existing.stamnummer else None
            owner_name = (
                f"{owner.voornaam} {owner.naam}" if owner else (existing.stamnummer or "?")
            )
            raise LaptopAlreadyLinkedError(
                f"Laptop {normalized_serial} is already linked to {owner_name} ({existing.stamnummer})."
            )

    # 3. Does this student already have an active (non-reserve) laptop?
    active_laptops = [lap for lap in student.laptops if lap.is_active and not lap.is_reserve]
    existing_match = next(
        (
            lap for lap in active_laptops
            if (is_own and lap.eigen_laptop)  # same eigen_laptop slot
            or (not is_own and lap.serial_number == normalized_serial)  # same serial
        ),
        None,
    )
    other_laptops = [lap for lap in active_laptops if lap is not existing_match]
    if other_laptops and not overwrite_existing:
        raise StudentAlreadyHasLaptopError(
            stamnummer=normalized_stamnummer,
            existing_serials=[describe_serial(lap) for lap in other_laptops],
        )

    # 4. Unlink the *other* active laptops when overwriting; keep the matching one.
    for lap in other_laptops:
        lap.unlinked_at = datetime.now()

    # Idempotent: this exact laptop is already linked to this student → no new record.
    if existing_match is not None:
        if other_laptops:
            session.commit()
            session.refresh(existing_match)
        return existing_match

    session.flush()

    # 5a. Magazijn-laptop: haal hetzelfde record uit het magazijn en ken het toe.
    #     Zo blijft er één actief record per serienummer (geen duplicaat).
    if from_magazijn is not None:
        from_magazijn.storage_cabinet_id = None
        from_magazijn.stamnummer = normalized_stamnummer
        from_magazijn.linked_at = datetime.now()
        from_magazijn.hoes_ingeleverd = True
        from_magazijn.oplader_ingeleverd = True
        session.commit()
        session.refresh(from_magazijn)
        return from_magazijn

    # 5b. Create the new laptop record.
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


def unlink_laptop(
    session: Session,
    laptop_id: int,
    hoes_ingeleverd: bool = True,
    oplader_ingeleverd: bool = True,
) -> Laptop:
    """Mark a laptop assignment as returned (ingeleverd).

    When the case (hoes) or charger (oplader) is missing, an issue is created
    automatically in the laptop issue tracker so the missing item is followed up.
    """
    laptop = session.get(Laptop, laptop_id)
    if laptop is None:
        raise LaptopNotFoundError("Laptop niet gevonden.")
    if laptop.unlinked_at is not None:
        raise LaptopAlreadyUnlinkedError("Laptop is al ingeleverd.")
    laptop.unlinked_at = datetime.now()
    laptop.hoes_ingeleverd = hoes_ingeleverd
    laptop.oplader_ingeleverd = oplader_ingeleverd

    if (not hoes_ingeleverd or not oplader_ingeleverd) and laptop.serial_number:
        missing: list[str] = []
        if not hoes_ingeleverd:
            missing.append("hoes")
        if not oplader_ingeleverd:
            missing.append("oplader")
        session.add(
            LaptopIssue(
                serial_number=laptop.serial_number,
                description=f"Bij inlevering ontbraken: {', '.join(missing)}.",
                reported_date=date.today(),
                status="aangemeld",
                category="Accessoires",
            )
        )

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
    """Return all laptop records with joined student/cabinet info, optionally filtered.

    ``kind`` can be ``"all"`` (default), ``"normal"`` (excludes reserve and cabinet),
    ``"reserve"`` (only reserve laptops), ``"cabinet"`` (only kast laptops), or
    ``"magazijn"`` (only magazijn laptops).
    """
    stmt = (
        select(
            Laptop,
            Student.naam,
            Student.voornaam,
            Student.klas,
            StorageCabinet.name.label("cabinet_name"),
            StorageCabinet.location.label("cabinet_location"),
            StorageCabinet.kind.label("cabinet_kind"),
        )
        .outerjoin(Student, Student.stamnummer == Laptop.stamnummer)
        .outerjoin(StorageCabinet, StorageCabinet.id == Laptop.storage_cabinet_id)
        # MariaDB does not support NULLS LAST syntax — use ISNULL to sort NULLs last.
        .order_by(func.isnull(Laptop.linked_at).asc(), Laptop.linked_at.desc(), Laptop.id.desc())
    )

    if kind == "reserve":
        stmt = stmt.where(Laptop.is_reserve.is_(True))
    elif kind == "cabinet":
        stmt = stmt.where(
            Laptop.storage_cabinet_id.isnot(None),
            StorageCabinet.kind == "kast",
        )
    elif kind == "magazijn":
        stmt = stmt.where(
            Laptop.storage_cabinet_id.isnot(None),
            StorageCabinet.kind == "magazijn",
        )
    elif kind == "normal":
        stmt = stmt.where(
            Laptop.is_reserve.is_(False),
            Laptop.storage_cabinet_id.is_(None),
        )

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
                f"{row.naam or ''} {row.voornaam or ''} {row.klas or ''} "
                f"{row.cabinet_name or ''} {row.cabinet_location or ''}"
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
            "storage_cabinet_id": row.Laptop.storage_cabinet_id,
            "cabinet_name": row.cabinet_name,
            "cabinet_location": row.cabinet_location,
            "cabinet_kind": row.cabinet_kind,
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
    storage_cabinet_id: int | None = None,
) -> Laptop:
    """Create a new laptop record.

    Three mutually-exclusive types:
    - Regular laptop: ``stamnummer`` and ``serial_number`` required.
    - Reserve laptop: ``is_reserve=True`` and ``alias`` required; no stamnummer/cabinet.
    - Cabinet laptop: ``storage_cabinet_id`` and ``serial_number`` required; no stamnummer/reserve.
    """
    normalized_serial = (serial_number or "").strip() or None
    normalized_stamnummer = (stamnummer or "").strip() or None
    normalized_alias = (alias or "").strip() or None

    if is_reserve and storage_cabinet_id is not None:
        raise LaptopValidationError(
            "Een laptop kan niet tegelijk reserve en in een uitleenkast zijn."
        )

    if storage_cabinet_id is not None:
        if normalized_stamnummer:
            raise LaptopValidationError(
                "Een kast-laptop mag niet aan een leerling gekoppeld zijn."
            )
        if not normalized_serial:
            raise LaptopValidationError("Serienummer is verplicht voor een kast-laptop.")
        cabinet = session.get(StorageCabinet, storage_cabinet_id)
        if cabinet is None:
            raise LaptopValidationError(
                f"Uitleenkast {storage_cabinet_id} bestaat niet."
            )
    elif is_reserve:
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

    if normalized_serial and not is_reserve:
        existing = session.scalars(
            select(Laptop).where(
                Laptop.serial_number == normalized_serial,
                Laptop.unlinked_at.is_(None),
                Laptop.is_reserve.is_(False),
            )
        ).first()
        if existing is not None:
            raise LaptopAlreadyLinkedError(
                f"Serienummer {normalized_serial} is al actief gekoppeld."
            )

    laptop = Laptop(
        serial_number=normalized_serial,
        stamnummer=None if (is_reserve or storage_cabinet_id is not None) else normalized_stamnummer,
        eigen_laptop=False,
        is_reserve=is_reserve,
        alias=normalized_alias,
        storage_cabinet_id=storage_cabinet_id,
        linked_at=None if is_reserve else datetime.now(),
    )
    session.add(laptop)
    session.commit()
    session.refresh(laptop)
    return laptop


def _next_reserve_alias_number(session: Session) -> int:
    """Hoogste bestaande ``Reserve-N``-nummer + 1 (default 1)."""
    aliases = session.scalars(
        select(Laptop.alias).where(
            Laptop.is_reserve.is_(True), Laptop.alias.isnot(None)
        )
    ).all()
    highest = 0
    for alias in aliases:
        match = _RESERVE_ALIAS_RE.match(alias or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def bulk_create_laptops(
    session: Session,
    serials: list[str],
    *,
    is_reserve: bool = False,
    storage_cabinet_id: int | None = None,
) -> dict:
    """Maak meerdere reserve- of kast-laptops aan vanuit een lijst serienummers.

    - Reserve: aliassen worden automatisch genummerd (``Reserve-N``).
    - Kast: ``storage_cabinet_id`` is verplicht en de kast moet bestaan.
    Dubbele serials binnen de invoer en al actief gekoppelde serials worden
    overgeslagen. Retourneert ``{created, skipped, errors}``.
    """
    if is_reserve and storage_cabinet_id is not None:
        raise LaptopValidationError(
            "Een laptop kan niet tegelijk reserve en in een uitleenkast zijn."
        )
    if not is_reserve and storage_cabinet_id is None:
        raise LaptopValidationError(
            "Kies een doel: reserve-pool of een uitleenkast."
        )

    if storage_cabinet_id is not None:
        cabinet = session.get(StorageCabinet, storage_cabinet_id)
        if cabinet is None:
            raise LaptopValidationError(f"Uitleenkast {storage_cabinet_id} bestaat niet.")

    created = 0
    skipped = 0
    errors: list[str] = []
    seen: set[str] = set()
    next_alias = _next_reserve_alias_number(session) if is_reserve else 0

    for raw in serials:
        serial = (raw or "").strip()
        if not serial:
            continue
        if not _SERIAL_RE.fullmatch(serial):
            errors.append(f"Ongeldig serienummer: {serial}")
            continue
        if serial in seen:
            skipped += 1
            continue
        seen.add(serial)

        if is_reserve:
            existing = session.scalars(
                select(Laptop).where(
                    Laptop.serial_number == serial,
                    Laptop.is_reserve.is_(True),
                )
            ).first()
            if existing is not None:
                skipped += 1
                continue
            session.add(Laptop(
                serial_number=serial,
                is_reserve=True,
                alias=f"Reserve-{next_alias}",
                linked_at=None,
            ))
            next_alias += 1
            created += 1
        else:
            existing = session.scalars(
                select(Laptop).where(
                    Laptop.serial_number == serial,
                    Laptop.unlinked_at.is_(None),
                    Laptop.is_reserve.is_(False),
                )
            ).first()
            if existing is not None:
                skipped += 1
                continue
            session.add(Laptop(
                serial_number=serial,
                storage_cabinet_id=storage_cabinet_id,
                linked_at=datetime.now(),
            ))
            created += 1

    session.commit()
    return {"created": created, "skipped": skipped, "errors": errors}


_UNSET = object()


def update_laptop(
    session: Session,
    laptop_id: int,
    serial_number: str | None = None,
    stamnummer: str | None = None,
    is_reserve: bool | None = None,
    alias: str | None = None,
    storage_cabinet_id=_UNSET,
) -> Laptop:
    """Update fields of a laptop record.

    ``storage_cabinet_id`` accepts an int (assign), ``None`` (clear) or the sentinel
    ``_UNSET`` (no change).
    """
    laptop = session.get(Laptop, laptop_id)
    if laptop is None:
        raise LaptopNotFoundError("Laptop niet gevonden.")

    if is_reserve is not None and is_reserve != laptop.is_reserve:
        if is_reserve:
            laptop.is_reserve = True
            laptop.stamnummer = None
            laptop.storage_cabinet_id = None
            if laptop.unlinked_at is None and laptop.linked_at is not None:
                laptop.unlinked_at = datetime.now()
        else:
            laptop.is_reserve = False

    if storage_cabinet_id is not _UNSET:
        if storage_cabinet_id is not None:
            cabinet = session.get(StorageCabinet, storage_cabinet_id)
            if cabinet is None:
                raise LaptopValidationError(
                    f"Uitleenkast {storage_cabinet_id} bestaat niet."
                )
            laptop.storage_cabinet_id = storage_cabinet_id
            laptop.stamnummer = None
            laptop.is_reserve = False
        else:
            laptop.storage_cabinet_id = None

    if alias is not None:
        normalized = alias.strip()
        laptop.alias = normalized or None

    if stamnummer is not None and not laptop.is_reserve and laptop.storage_cabinet_id is None:
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
                    f"Serienummer {normalized} is al actief gekoppeld aan een andere laptop."
                )
        laptop.serial_number = normalized

    if laptop.is_reserve and not laptop.alias:
        raise LaptopValidationError("Reserve-laptop vereist een alias.")
    if laptop.storage_cabinet_id is not None and not laptop.serial_number:
        raise LaptopValidationError("Serienummer is verplicht voor een kast-laptop.")

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
