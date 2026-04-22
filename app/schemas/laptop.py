from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LaptopLinkRequest(BaseModel):
    stamnummer: str
    serial_number: str
    overwrite_existing: bool = False


class LaptopLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    serial_number: str | None  # None for eigen laptop
    stamnummer: str
    eigen_laptop: bool
    linked_at: datetime | None = None
    unlinked_at: datetime | None = None


class LaptopCreate(BaseModel):
    serial_number: str
    stamnummer: str


class LaptopUpdate(BaseModel):
    serial_number: str | None = None
    stamnummer: str | None = None


class LaptopListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    serial_number: str | None
    stamnummer: str
    eigen_laptop: bool
    linked_at: datetime | None = None
    unlinked_at: datetime | None = None
    is_active: bool
    naam: str | None = None
    voornaam: str | None = None
    klas: str | None = None


class LaptopImportResult(BaseModel):
    created: int
    updated: int
    errors: list[str]
