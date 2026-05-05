from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StorageCabinetCreate(BaseModel):
    name: str
    location: str | None = None
    description: str | None = None
    capacity: int | None = None


class StorageCabinetUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    description: str | None = None
    capacity: int | None = None


class StorageCabinetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str | None = None
    description: str | None = None
    capacity: int | None = None
    created_at: datetime | None = None
    laptop_count: int = 0


class StorageCabinetDeleteRequest(BaseModel):
    ids: list[int]


class StorageCabinetDeleteResponse(BaseModel):
    deleted: int
