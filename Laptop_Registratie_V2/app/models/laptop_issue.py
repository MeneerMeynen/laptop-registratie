from sqlalchemy import Column, Date, DateTime, Integer, String, Text, text

from app.db import Base


class LaptopIssue(Base):
    __tablename__ = "laptop_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=False)
    reported_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, server_default="open")
    solution = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("NOW()"))
