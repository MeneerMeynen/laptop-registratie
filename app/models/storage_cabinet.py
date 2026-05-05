from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class StorageCabinet(Base):
    __tablename__ = "storage_cabinets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    location = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    capacity = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    laptops = relationship("Laptop", back_populates="storage_cabinet")
