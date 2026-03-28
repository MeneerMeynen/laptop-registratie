"""Add unlinked_at column and drop unique constraint on serial_number.

This enables laptop assignment history: each row represents a period
during which a student had a laptop. Active assignments have
unlinked_at = NULL.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "laptops",
        sa.Column("unlinked_at", sa.DateTime(), nullable=True),
    )
    # Drop unique constraint so one serial can have multiple history rows.
    # MariaDB names the constraint after the column by default.
    op.drop_constraint("serial_number", "laptops", type_="unique")
    # Index for fast lookup of active assignments per serial.
    op.create_index(
        "ix_laptops_serial_active",
        "laptops",
        ["serial_number", "unlinked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_laptops_serial_active", table_name="laptops")
    op.create_unique_constraint("serial_number", "laptops", ["serial_number"])
    op.drop_column("laptops", "unlinked_at")
