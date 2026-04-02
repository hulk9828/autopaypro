"""add admins table

Revision ID: 44e10796df7f
Revises: 033ce8cec070
Create Date: 2026-01-19 18:29:47.217489

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44e10796df7f'
down_revision: Union[str, None] = '033ce8cec070'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This revision duplicated base schema creation; keep as no-op.
    pass


def downgrade() -> None:
    pass
