"""Add storage cabinets: storage_cabinets table + storage_cabinet_id FK on laptops.

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "storage_cabinets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name="uq_storage_cabinets_name"),
    )

    op.add_column(
        "laptops",
        sa.Column("storage_cabinet_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_laptops_storage_cabinet_id",
        "laptops",
        ["storage_cabinet_id"],
    )
    op.create_foreign_key(
        "fk_laptops_storage_cabinet_id",
        "laptops",
        "storage_cabinets",
        ["storage_cabinet_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_laptops_storage_cabinet_id",
        "laptops",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_laptops_storage_cabinet_id",
        table_name="laptops",
    )
    op.drop_column("laptops", "storage_cabinet_id")

    op.drop_table("storage_cabinets")
