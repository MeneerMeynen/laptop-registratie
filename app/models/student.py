from sqlalchemy import Column, String, DateTime
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
    last_import = Column(DateTime, nullable=True)

    laptops = relationship(
        "Laptop",
        back_populates="student",
        cascade="all, delete-orphan",
    )
