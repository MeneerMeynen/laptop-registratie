from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LaptopLinkRequest(BaseModel):
    stamnummer: str
    serial_number: str
    overwrite_existing: bool = False


class LaptopUnlinkRequest(BaseModel):
    hoes_ingeleverd: bool = True
    oplader_ingeleverd: bool = True


class LaptopLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    serial_number: str | None  # None for eigen laptop
    stamnummer: str | None
    eigen_laptop: bool
    is_reserve: bool = False
    alias: str | None = None
    storage_cabinet_id: int | None = None
    linked_at: datetime | None = None
    unlinked_at: datetime | None = None
    hoes_ingeleverd: bool = True
    oplader_ingeleverd: bool = True


class LaptopCreate(BaseModel):
    serial_number: str | None = None
    stamnummer: str | None = None
    is_reserve: bool = False
    alias: str | None = None
    storage_cabinet_id: int | None = None


class LaptopUpdate(BaseModel):
    serial_number: str | None = None
    stamnummer: str | None = None
    is_reserve: bool | None = None
    alias: str | None = None
    storage_cabinet_id: int | None = None


class LaptopListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    serial_number: str | None
    stamnummer: str | None
    eigen_laptop: bool
    is_reserve: bool = False
    alias: str | None = None
    linked_at: datetime | None = None
    unlinked_at: datetime | None = None
    is_active: bool
    naam: str | None = None
    voornaam: str | None = None
    klas: str | None = None
    hoes_ingeleverd: bool = True
    oplader_ingeleverd: bool = True


class LaptopImportResult(BaseModel):
    created: int
    updated: int
    errors: list[str]


class LaptopBulkCreate(BaseModel):
    serials: list[str]
    is_reserve: bool = False
    storage_cabinet_id: int | None = None


class LaptopBulkResult(BaseModel):
    created: int
    skipped: int
    errors: list[str]


class ReserveLaptopOption(BaseModel):
    id: int
    alias: str | None = None
    serial_number: str | None = None
    in_use_by_issue_id: int | None = None
    in_use_by_student: str | None = None
