"""create users table

Revision ID: 3d50ef457874
Revises: 2e460971fe8c
Create Date: 2026-01-19 17:41:51.243399

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d50ef457874'
down_revision: Union[str, None] = '2e460971fe8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This revision duplicated initial table creation; keep as no-op.
    pass


def downgrade() -> None:
    pass
