"""Add linked_at column to laptops table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "laptops",
        sa.Column("linked_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("laptops", "linked_at")
