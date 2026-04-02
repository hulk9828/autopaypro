"""create users table

Revision ID: 033ce8cec070
Revises: dd7e3f736937
Create Date: 2026-01-19 18:17:57.524133

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '033ce8cec070'
down_revision: Union[str, None] = 'dd7e3f736937'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This revision duplicated base schema creation; keep as no-op.
    pass


def downgrade() -> None:
    pass
