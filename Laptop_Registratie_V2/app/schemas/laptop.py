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
