"""Add is_leerkracht column to students.

Teachers are stored in the same ``students`` table so that linking, issues,
photos and exports work unchanged. The flag separates both groups in the UI
and scopes the "Uitgeschreven" badge per group (a teacher import must not
mark all students as uitgeschreven and vice versa).

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column(
            "is_leerkracht",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("students", "is_leerkracht")
