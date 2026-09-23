from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import relationship

from app.db import Base


class Student(Base):
    __tablename__ = "students"

    stamnummer = Column(String(50), primary_key=True)
    instellingsnummer = Column(String(50), nullable=True)
    naam = Column(String(100), nullable=True)
    voornaam = Column(String(100), nullable=True)
    klas = Column(String(50), nullable=True)
    klascode = Column(String(50), nullable=True)
    klasnummer = Column(String(50), nullable=True)
    gebruikersnaam = Column(String(100), nullable=True)
    pointer = Column(String(100), nullable=True)
    # Staff abbreviation from the leerkrachten-export (e.g. ANTCE).
    afkorting = Column(String(20), nullable=True)
    last_import = Column(DateTime, nullable=True)
    # Teachers share this table so linking, issues and exports work unchanged.
    is_leerkracht = Column(Boolean, default=False, nullable=False, server_default="0")

    laptops = relationship(
        "Laptop",
        back_populates="student",
        cascade="all, delete-orphan",
    )
