from sqlalchemy import Column, DateTime, Integer, String, text

from app.db import Base


class LaptopPhoto(Base):
    __tablename__ = "laptop_photos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String(100), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("NOW()"))
