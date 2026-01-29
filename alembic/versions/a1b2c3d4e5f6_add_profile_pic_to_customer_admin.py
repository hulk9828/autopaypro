"""add profile_pic to customer and admin

Revision ID: a1b2c3d4e5f6
Revises: 79bbdc53ad56
Create Date: 2026-01-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '79bbdc53ad56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('profile_pic', sa.String(), nullable=True))
    op.add_column('admins', sa.Column('profile_pic', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'profile_pic')
    op.drop_column('admins', 'profile_pic')
