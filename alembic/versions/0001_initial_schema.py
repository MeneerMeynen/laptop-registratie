"""Initial schema: students and laptops tables.

Revision ID: 0001
Revises:
Create Date: 2026-03-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("stamnummer", sa.String(50), nullable=False),
        sa.Column("instellingsnummer", sa.String(50), nullable=True),
        sa.Column("naam", sa.String(100), nullable=True),
        sa.Column("voornaam", sa.String(100), nullable=True),
        sa.Column("klas", sa.String(50), nullable=True),
        sa.Column("klascode", sa.String(50), nullable=True),
        sa.Column("klasnummer", sa.String(50), nullable=True),
        sa.Column("gebruikersnaam", sa.String(100), nullable=True),
        sa.Column("pointer", sa.String(100), nullable=True),
        sa.Column("last_import", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("stamnummer"),
    )

    op.create_table(
        "laptops",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("stamnummer", sa.String(50), nullable=False),
        sa.Column("eigen_laptop", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["stamnummer"], ["students.stamnummer"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("serial_number"),
    )
    op.create_index("ix_laptops_stamnummer", "laptops", ["stamnummer"])


def downgrade() -> None:
    op.drop_index("ix_laptops_stamnummer", table_name="laptops")
    op.drop_table("laptops")
    op.drop_table("students")
