import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from sqlalchemy.orm import Session

from app.models.student import Student


def import_students_from_stream(session: Session, csv_stream: TextIO) -> int:
    """Parse a semicolon-delimited CSV and upsert students into the database.

    Sets ``last_import`` on every touched record so that students absent from
    the most recent import can be identified as "Uitgeschreven".

    Returns the number of records processed.
    """
    imported_count = 0
    import_timestamp = datetime.now(timezone.utc)
    reader = csv.DictReader(csv_stream, delimiter=";")

    for row in reader:
        stamnummer = (row.get("Stamnummer") or "").strip()
        if not stamnummer:
            continue

        student = session.get(Student, stamnummer)
        if student is None:
            student = Student(stamnummer=stamnummer)
            session.add(student)

        student.instellingsnummer = (row.get("Instellingsnummer") or "").strip()
        student.naam = (row.get("Naam") or "").strip()
        student.voornaam = (row.get("Voornaam") or "").strip()
        student.klas = (row.get("Klas") or "").strip()
        student.klascode = (row.get("Klascode") or "").strip()
        student.klasnummer = (row.get("Klasnummer") or "").strip()
        student.gebruikersnaam = (row.get("Gebruikersnaam") or "").strip()
        student.pointer = (row.get("Pointer") or "").strip()
        student.last_import = import_timestamp
        imported_count += 1

    session.commit()
    return imported_count


def import_students_from_csv(session: Session, csv_path: Path) -> int:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return import_students_from_stream(session, csv_file)
