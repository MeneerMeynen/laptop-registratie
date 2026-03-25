from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy import text as sa_text

from app.db import Base


class LaptopIssueEntry(Base):
    __tablename__ = "laptop_issue_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(
        Integer,
        ForeignKey("laptop_issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=sa_text("NOW()"))
