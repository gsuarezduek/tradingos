"""operar: trading_enabled y live_orders

Revision ID: f3a1c9e5b7d2
Revises: dd0867c88329
Create Date: 2026-07-25 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a1c9e5b7d2"
down_revision: Union[str, Sequence[str], None] = "dd0867c88329"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("broker_connections", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("trading_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false"))
        )

    op.create_table(
        "live_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("broker_connection_id", sa.Integer(), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("exchange_order_id", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("live_orders", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_live_orders_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_live_orders_broker_connection_id"), ["broker_connection_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("live_orders", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_live_orders_broker_connection_id"))
        batch_op.drop_index(batch_op.f("ix_live_orders_user_id"))
    op.drop_table("live_orders")

    with op.batch_alter_table("broker_connections", schema=None) as batch_op:
        batch_op.drop_column("trading_enabled")
