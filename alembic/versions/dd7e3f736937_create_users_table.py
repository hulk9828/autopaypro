"""create users table

Revision ID: dd7e3f736937
Revises: 3d50ef457874
Create Date: 2026-01-19 17:57:49.001375

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd7e3f736937'
down_revision: Union[str, None] = '3d50ef457874'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This revision duplicated base schema creation; keep as no-op.
    pass


def downgrade() -> None:
    pass
