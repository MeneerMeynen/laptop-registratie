from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db import Base


class Laptop(Base):
    __tablename__ = "laptops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # nullable=True so "eigen laptop" records have no serial.
    serial_number = Column(String(100), nullable=True, index=True)
    # nullable=True so reserve laptops can sit in inventory without a student.
    stamnummer = Column(
        String(50),
        ForeignKey("students.stamnummer", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    eigen_laptop = Column(Boolean, default=False, nullable=False)
    is_reserve = Column(Boolean, default=False, nullable=False, server_default="0")
    alias = Column(String(100), nullable=True)
    storage_cabinet_id = Column(
        Integer,
        ForeignKey("storage_cabinets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    linked_at = Column(DateTime, nullable=True)
    unlinked_at = Column(DateTime, nullable=True)
    hoes_ingeleverd = Column(Boolean, default=True, nullable=False, server_default="1")
    oplader_ingeleverd = Column(Boolean, default=True, nullable=False, server_default="1")

    @property
    def is_active(self) -> bool:
        return self.unlinked_at is None

    student = relationship("Student", back_populates="laptops")
    storage_cabinet = relationship("StorageCabinet", back_populates="laptops")
