"""Data for the printable gebruiksovereenkomst (user agreement), students only."""
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.laptop import Laptop
from app.models.student import Student

MAANDEN = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]


class ContractError(Exception):
    """Raised when no contract can be generated for the given person."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def schooljaar(d: date) -> str:
    """School year label for a date; a new school year starts in August."""
    start = d.year if d.month >= 8 else d.year - 1
    return f"{start}-{start + 1}"


def datum_nl(d: date) -> str:
    return f"{d.day} {MAANDEN[d.month - 1]} {d.year}"


def get_contract_context(db: Session, stamnummer: str) -> dict:
    """Return the template context for a contract, or raise ``ContractError``.

    Uses the student's active, school-owned laptop (no eigen laptop / reserve).
    Teachers get no contract.
    """
    student = db.get(Student, stamnummer)
    if student is None:
        raise ContractError("Leerling niet gevonden.", status_code=404)
    if student.is_leerkracht:
        raise ContractError("Er is geen gebruiksovereenkomst voor leerkrachten.", status_code=404)

    laptop = db.execute(
        select(Laptop)
        .where(Laptop.stamnummer == stamnummer)
        .where(Laptop.unlinked_at.is_(None))
        .where(Laptop.eigen_laptop.is_(False))
        .order_by(Laptop.linked_at.desc(), Laptop.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if laptop is None:
        raise ContractError(
            "Geen schoollaptop gekoppeld; er kan geen contract worden opgemaakt.",
            status_code=404,
        )

    linked = laptop.linked_at or datetime.now()
    return {
        "student": student,
        "laptop": laptop,
        "schooljaar": schooljaar(linked.date()),
        "opgemaakt_op": datum_nl(linked.date()),
    }
