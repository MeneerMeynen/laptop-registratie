"""Add afkorting column to students.

The leerkrachten-export carries an "Afkorting" (e.g. ANTCE) that staff use to
identify each other; it is shown in the lists and included in the search.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("students", sa.Column("afkorting", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("students", "afkorting")
