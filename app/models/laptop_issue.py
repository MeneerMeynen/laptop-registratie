from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, text

from app.db import Base


class LaptopIssue(Base):
    __tablename__ = "laptop_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=False)
    reported_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, server_default="aangemeld")
    solution = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    reserve_laptop_id = Column(
        Integer,
        ForeignKey("laptops.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("NOW()"))
