from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LaptopInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    serial_number: str | None
    eigen_laptop: bool


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stamnummer: str
    instellingsnummer: str | None = None
    naam: str | None = None
    voornaam: str | None = None
    klas: str | None = None
    klascode: str | None = None
    klasnummer: str | None = None
    gebruikersnaam: str | None = None
    pointer: str | None = None
    last_import: datetime | None = None
    laptops: list[LaptopInfo] = []


class StudentDeleteRequest(BaseModel):
    stamnummers: list[str]


class StudentDeleteResponse(BaseModel):
    deleted: int


class StudentCreate(BaseModel):
    stamnummer: str
    instellingsnummer: str | None = None
    naam: str | None = None
    voornaam: str | None = None
    klas: str | None = None
    klascode: str | None = None
    klasnummer: str | None = None
    gebruikersnaam: str | None = None
    pointer: str | None = None


class StudentUpdate(BaseModel):
    instellingsnummer: str | None = None
    naam: str | None = None
    voornaam: str | None = None
    klas: str | None = None
    klascode: str | None = None
    klasnummer: str | None = None
    gebruikersnaam: str | None = None
    pointer: str | None = None
