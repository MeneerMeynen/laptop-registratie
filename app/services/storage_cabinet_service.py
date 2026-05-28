from datetime import datetime
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.laptop import Laptop
from app.models.storage_cabinet import StorageCabinet


class StorageCabinetValidationError(ValueError):
    pass


class StorageCabinetNotFoundError(ValueError):
    pass


class StorageCabinetAlreadyExistsError(ValueError):
    pass


class StorageCabinetInUseError(ValueError):
    def __init__(self, cabinet_ids: list[int]):
        self.cabinet_ids = cabinet_ids
        super().__init__(
            "Eén of meer locaties bevatten nog laptops. Verplaats die laptops eerst."
        )


_VALID_KINDS = ("kast", "magazijn")


def _serialize(cabinet: StorageCabinet, laptop_count: int = 0) -> dict:
    return {
        "id": cabinet.id,
        "name": cabinet.name,
        "kind": cabinet.kind,
        "location": cabinet.location,
        "description": cabinet.description,
        "capacity": cabinet.capacity,
        "created_at": cabinet.created_at,
        "laptop_count": laptop_count,
    }


def list_cabinets(
    session: Session, q: str | None = None, kind: str | None = None
) -> list[dict]:
    """Return all cabinets with the count of currently-attached laptops.

    ``kind`` filtert optioneel op ``"kast"`` of ``"magazijn"``.
    """
    count_subq = (
        select(
            Laptop.storage_cabinet_id.label("cabinet_id"),
            func.count(Laptop.id).label("laptop_count"),
        )
        .where(Laptop.storage_cabinet_id.isnot(None))
        .group_by(Laptop.storage_cabinet_id)
        .subquery()
    )

    stmt = (
        select(StorageCabinet, count_subq.c.laptop_count)
        .outerjoin(count_subq, count_subq.c.cabinet_id == StorageCabinet.id)
        .order_by(StorageCabinet.name.asc())
    )
    if kind is not None:
        stmt = stmt.where(StorageCabinet.kind == kind)

    rows = session.execute(stmt).all()
    results = []
    for row in rows:
        cabinet = row.StorageCabinet
        if q:
            q_lower = q.lower()
            searchable = (
                f"{cabinet.name or ''} {cabinet.location or ''} {cabinet.description or ''}"
            ).lower()
            if q_lower not in searchable:
                continue
        results.append(_serialize(cabinet, laptop_count=row.laptop_count or 0))
    return results


def get_cabinet(session: Session, cabinet_id: int) -> StorageCabinet:
    cabinet = session.get(StorageCabinet, cabinet_id)
    if cabinet is None:
        raise StorageCabinetNotFoundError(f"Uitleenkast {cabinet_id} bestaat niet.")
    return cabinet


def _normalize_capacity(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise StorageCabinetValidationError("Capaciteit moet een geheel getal zijn.")
    if n < 0:
        raise StorageCabinetValidationError("Capaciteit kan niet negatief zijn.")
    return n


def create_cabinet(
    session: Session,
    *,
    name: str,
    kind: str = "kast",
    location: str | None = None,
    description: str | None = None,
    capacity: int | None = None,
) -> StorageCabinet:
    normalized_name = (name or "").strip()
    if not normalized_name:
        raise StorageCabinetValidationError("Naam is verplicht.")
    if kind not in _VALID_KINDS:
        raise StorageCabinetValidationError(f"Ongeldig type: {kind}.")

    existing = session.scalars(
        select(StorageCabinet).where(StorageCabinet.name == normalized_name)
    ).first()
    if existing is not None:
        raise StorageCabinetAlreadyExistsError(
            f"Locatie met naam '{normalized_name}' bestaat al."
        )

    cabinet = StorageCabinet(
        name=normalized_name,
        kind=kind,
        location=(location or "").strip() or None,
        description=(description or "").strip() or None,
        capacity=_normalize_capacity(capacity),
        created_at=datetime.now(),
    )
    session.add(cabinet)
    session.commit()
    session.refresh(cabinet)
    return cabinet


def update_cabinet(
    session: Session,
    cabinet_id: int,
    *,
    name: str | None = None,
    location: str | None = None,
    description: str | None = None,
    capacity=None,
) -> StorageCabinet:
    cabinet = get_cabinet(session, cabinet_id)

    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise StorageCabinetValidationError("Naam mag niet leeg zijn.")
        if normalized_name != cabinet.name:
            conflict = session.scalars(
                select(StorageCabinet).where(
                    StorageCabinet.name == normalized_name,
                    StorageCabinet.id != cabinet_id,
                )
            ).first()
            if conflict is not None:
                raise StorageCabinetAlreadyExistsError(
                    f"Uitleenkast met naam '{normalized_name}' bestaat al."
                )
        cabinet.name = normalized_name

    if location is not None:
        cabinet.location = location.strip() or None

    if description is not None:
        cabinet.description = description.strip() or None

    if capacity is not None:
        cabinet.capacity = _normalize_capacity(capacity)

    session.commit()
    session.refresh(cabinet)
    return cabinet


def delete_cabinets(session: Session, ids: Iterable[int]) -> int:
    """Hard-delete cabinets. Refuses if any cabinet still holds laptops."""
    id_list = [int(i) for i in ids]
    if not id_list:
        return 0

    in_use_ids = list(
        session.scalars(
            select(Laptop.storage_cabinet_id)
            .where(Laptop.storage_cabinet_id.in_(id_list))
            .distinct()
        )
    )
    if in_use_ids:
        raise StorageCabinetInUseError(in_use_ids)

    cabinets = list(
        session.scalars(select(StorageCabinet).where(StorageCabinet.id.in_(id_list)))
    )
    for cabinet in cabinets:
        session.delete(cabinet)
    session.commit()
    return len(cabinets)
