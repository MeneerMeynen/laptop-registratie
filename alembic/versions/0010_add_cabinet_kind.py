"""Add kind discriminator to storage_cabinets (kast vs magazijn).

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "storage_cabinets",
        sa.Column(
            "kind",
            sa.String(length=20),
            nullable=False,
            server_default="kast",
        ),
    )


def downgrade() -> None:
    op.drop_column("storage_cabinets", "kind")
