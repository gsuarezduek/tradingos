"""reglas de condiciones en estrategias guardadas

Revision ID: d3464c20a891
Revises: f3a1c9e5b7d2
Create Date: 2026-07-25 21:20:14.968240

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3464c20a891'
down_revision: Union[str, Sequence[str], None] = 'f3a1c9e5b7d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nota: el autogenerate también detectó 'live_orders.created_at' como columna a
    # borrar — es una inconsistencia de otro trabajo en curso (modelo de live_orders
    # vs. su propia migración previa), no relacionada con esta migración. Se omite acá
    # a propósito para no pisar ese cambio ajeno.
    with op.batch_alter_table('saved_strategies', schema=None) as batch_op:
        batch_op.add_column(sa.Column('entry_rules', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('exit_rules', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('saved_strategies', schema=None) as batch_op:
        batch_op.drop_column('exit_rules')
        batch_op.drop_column('entry_rules')
