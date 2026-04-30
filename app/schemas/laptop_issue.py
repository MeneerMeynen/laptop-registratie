from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


_UNSET = object()


class LaptopIssueCreate(BaseModel):
    serial_number: str
    description: str
    reported_date: date
    category: Optional[str] = None
    reserve_laptop_id: Optional[int] = None


class LaptopIssueUpdate(BaseModel):
    description: Optional[str] = None
    reported_date: Optional[date] = None
    status: Optional[str] = None
    solution: Optional[str] = None
    category: Optional[str] = None
    # When the field is omitted from the request body it stays untouched;
    # explicit None means "release the reserve laptop".
    reserve_laptop_id: Optional[int] = Field(default=None)

    model_config = {"json_schema_extra": {}}


class LaptopIssueRead(BaseModel):
    id: int
    serial_number: str
    description: str
    reported_date: date
    status: str
    solution: Optional[str] = None
    category: Optional[str] = None
    naam: Optional[str] = None
    voornaam: Optional[str] = None
    stamnummer: Optional[str] = None
    reserve_laptop_id: Optional[int] = None
    reserve_laptop_alias: Optional[str] = None
    reserve_laptop_serial: Optional[str] = None

    model_config = {"from_attributes": True}
