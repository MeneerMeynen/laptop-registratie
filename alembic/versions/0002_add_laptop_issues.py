"""Add laptop_issues table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "laptop_issues",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("reported_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("solution", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_laptop_issues_serial_number", "laptop_issues", ["serial_number"])
    op.create_index("ix_laptop_issues_status", "laptop_issues", ["status"])


def downgrade() -> None:
    op.drop_index("ix_laptop_issues_status", table_name="laptop_issues")
    op.drop_index("ix_laptop_issues_serial_number", table_name="laptop_issues")
    op.drop_table("laptop_issues")