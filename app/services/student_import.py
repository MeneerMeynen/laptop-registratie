import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from sqlalchemy.orm import Session

from app.models.student import Student

_FIELDS = (
    "instellingsnummer",
    "naam",
    "voornaam",
    "klas",
    "klascode",
    "klasnummer",
    "gebruikersnaam",
    "pointer",
    "afkorting",
)

# Header aliases: the leerkrachten-export uses slightly different column names
# than the leerlingen-export. Keys are the normalized (lowercase) headers.
_HEADER_ALIASES = {
    "instellingsnummers": "instellingsnummer",
    "klasnr": "klasnummer",
}

# Columns in the leerkrachten-export that must never be stored (passwords,
# payment card and PIN data). Listed here so it's explicit, not accidental.
_IGNORED_COLUMNS = ("standaardpaswoord", "betaalkaart", "pincode")

_DELIMITERS = (";", "\t", ",")


def _sniff_delimiter(header_line: str) -> str:
    """Pick the delimiter that splits the header into the most columns."""
    return max(_DELIMITERS, key=header_line.count)


def _normalize_row(row: dict) -> dict[str, str]:
    """Normalize header names (lowercase, stripped, aliased) and strip values."""
    normalized: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        name = (key or "").strip().lower()
        name = _HEADER_ALIASES.get(name, name)
        if name in _IGNORED_COLUMNS:
            continue
        normalized[name] = (value or "").strip()
    return normalized


def import_students_from_stream(
    session: Session, csv_stream: TextIO, *, is_leerkracht: bool = False
) -> int:
    """Parse a CSV (semicolon-, tab- or comma-separated) and upsert students.

    Sets ``last_import`` on every touched record so that records absent from
    the most recent import of the same group can be identified as
    "Uitgeschreven".

    Teachers are identified by ``Stamnummer`` or, when that column is empty
    or missing, by ``Gebruikersnaam``. Rows whose identifier already belongs
    to the other group (student vs. teacher) are skipped, never converted.

    Returns the number of records processed.
    """
    imported_count = 0
    import_timestamp = datetime.now(timezone.utc)

    content = csv_stream.read()
    if not content.strip():
        return 0
    delimiter = _sniff_delimiter(content.splitlines()[0])
    reader = csv.DictReader(content.splitlines(), delimiter=delimiter)

    for raw_row in reader:
        row = _normalize_row(raw_row)
        stamnummer = row.get("stamnummer", "")
        if not stamnummer and is_leerkracht:
            stamnummer = row.get("gebruikersnaam", "")
        if not stamnummer:
            continue

        student = session.get(Student, stamnummer)
        if student is None:
            student = Student(stamnummer=stamnummer, is_leerkracht=is_leerkracht)
            session.add(student)
        elif bool(student.is_leerkracht) != is_leerkracht:
            continue

        for field in _FIELDS:
            setattr(student, field, row.get(field, ""))
        student.last_import = import_timestamp
        imported_count += 1

    session.commit()
    return imported_count


def import_students_from_csv(
    session: Session, csv_path: Path, *, is_leerkracht: bool = False
) -> int:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return import_students_from_stream(
            session, csv_file, is_leerkracht=is_leerkracht
        )
