"""Add reserve laptop support: is_reserve/alias on laptops, reserve_laptop_id on issues.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "laptops",
        sa.Column(
            "is_reserve",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "laptops",
        sa.Column("alias", sa.String(length=100), nullable=True),
    )
    # Allow stamnummer to be NULL so reserve laptops can sit in stock unassigned.
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.alter_column(
            "laptops",
            "stamnummer",
            existing_type=sa.String(length=50),
            nullable=True,
        )
    else:
        with op.batch_alter_table("laptops") as batch_op:
            batch_op.alter_column(
                "stamnummer",
                existing_type=sa.String(length=50),
                nullable=True,
            )

    op.add_column(
        "laptop_issues",
        sa.Column("reserve_laptop_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_laptop_issues_reserve_laptop_id",
        "laptop_issues",
        ["reserve_laptop_id"],
    )
    op.create_foreign_key(
        "fk_laptop_issues_reserve_laptop_id",
        "laptop_issues",
        "laptops",
        ["reserve_laptop_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_laptop_issues_reserve_laptop_id",
        "laptop_issues",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_laptop_issues_reserve_laptop_id",
        table_name="laptop_issues",
    )
    op.drop_column("laptop_issues", "reserve_laptop_id")

    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.alter_column(
            "laptops",
            "stamnummer",
            existing_type=sa.String(length=50),
            nullable=False,
        )
    else:
        with op.batch_alter_table("laptops") as batch_op:
            batch_op.alter_column(
                "stamnummer",
                existing_type=sa.String(length=50),
                nullable=False,
            )

    op.drop_column("laptops", "alias")
    op.drop_column("laptops", "is_reserve")
