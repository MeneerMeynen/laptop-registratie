"""Add hoes_ingeleverd and oplader_ingeleverd columns to laptops.

Tracks whether the laptop case (beschermhoes) and charger (oplader) were
returned along with the laptop at the moment of inlevering. Defaults to
True so existing records reflect the assumption that all accessories were
returned.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "laptops",
        sa.Column(
            "hoes_ingeleverd",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "laptops",
        sa.Column(
            "oplader_ingeleverd",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )


def downgrade() -> None:
    op.drop_column("laptops", "oplader_ingeleverd")
    op.drop_column("laptops", "hoes_ingeleverd")
