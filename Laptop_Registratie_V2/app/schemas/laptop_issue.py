from datetime import date
from typing import Optional

from pydantic import BaseModel


class LaptopIssueCreate(BaseModel):
    serial_number: str
    description: str
    reported_date: date


class LaptopIssueUpdate(BaseModel):
    description: Optional[str] = None
    reported_date: Optional[date] = None
    status: Optional[str] = None
    solution: Optional[str] = None


class LaptopIssueRead(BaseModel):
    id: int
    serial_number: str
    description: str
    reported_date: date
    status: str
    solution: Optional[str] = None
    naam: Optional[str] = None
    voornaam: Optional[str] = None
    stamnummer: Optional[str] = None

    model_config = {"from_attributes": True}
