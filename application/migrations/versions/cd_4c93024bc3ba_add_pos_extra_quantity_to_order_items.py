"""add pos extra quantity to order items

Revision ID: 4c93024bc3ba
Revises: 3101e853c140
Create Date: 2025-09-13 13:56:53.890990

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c93024bc3ba'
down_revision: Union[str, Sequence[str], None] = '3101e853c140'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('order_items', sa.Column('pos_extra_quantity', sa.Numeric(10, 2), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('order_items', 'pos_extra_quantity')
