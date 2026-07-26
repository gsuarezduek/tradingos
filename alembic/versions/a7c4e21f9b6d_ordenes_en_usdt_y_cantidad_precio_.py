"""ordenes: monto en USDT y cantidad/precio real ejecutado

Revision ID: a7c4e21f9b6d
Revises: 10470ba4bf07
Create Date: 2026-07-25 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7c4e21f9b6d"
down_revision: Union[str, Sequence[str], None] = "10470ba4bf07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("live_orders", schema=None) as batch_op:
        batch_op.alter_column("quantity", new_column_name="amount_usdt")
        batch_op.add_column(sa.Column("filled_quantity", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("avg_price", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("live_orders", schema=None) as batch_op:
        batch_op.drop_column("avg_price")
        batch_op.drop_column("filled_quantity")
        batch_op.alter_column("amount_usdt", new_column_name="quantity")
