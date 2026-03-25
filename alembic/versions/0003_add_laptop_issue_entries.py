"""Add laptop_issue_entries table.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "laptop_issue_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("issue_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["issue_id"], ["laptop_issues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_laptop_issue_entries_issue_id", "laptop_issue_entries", ["issue_id"])


def downgrade() -> None:
    op.drop_index("ix_laptop_issue_entries_issue_id", table_name="laptop_issue_entries")
    op.drop_table("laptop_issue_entries")
