from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db import Base


class Laptop(Base):
    __tablename__ = "laptops"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # nullable=True so "eigen laptop" records have no serial.
    serial_number = Column(String(100), nullable=True, index=True)
    stamnummer = Column(
        String(50),
        ForeignKey("students.stamnummer", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    eigen_laptop = Column(Boolean, default=False, nullable=False)
    linked_at = Column(DateTime, nullable=True)
    unlinked_at = Column(DateTime, nullable=True)

    @property
    def is_active(self) -> bool:
        return self.unlinked_at is None

    student = relationship("Student", back_populates="laptops")
