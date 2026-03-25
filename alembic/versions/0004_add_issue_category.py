"""Add category column to laptop_issues.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-25

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "laptop_issues",
        sa.Column("category", sa.String(50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("laptop_issues", "category")
