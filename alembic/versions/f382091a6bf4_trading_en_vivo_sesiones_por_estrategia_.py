"""trading en vivo: sesiones por estrategia y live_trades

Revision ID: f382091a6bf4
Revises: a7c4e21f9b6d
Create Date: 2026-07-25 23:18:28.180838

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f382091a6bf4'
down_revision: Union[str, Sequence[str], None] = 'a7c4e21f9b6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "live_trading_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.Integer(), nullable=False),
        sa.Column("broker_connection_id", sa.Integer(), nullable=False),
        sa.Column("exchange", sa.String(length=32), nullable=False),
        sa.Column("strategy", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_position", sa.JSON(), nullable=True),
        sa.Column("last_tick_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"]),
        sa.ForeignKeyConstraint(["strategy_id"], ["saved_strategies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("live_trading_sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_live_trading_sessions_user_id"), ["user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_live_trading_sessions_strategy_id"), ["strategy_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_live_trading_sessions_broker_connection_id"), ["broker_connection_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_live_trading_sessions_status"), ["status"], unique=False)

    op.create_table(
        "live_trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("entry_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("exit_price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("pnl", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["live_trading_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("live_trades", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_live_trades_session_id"), ["session_id"], unique=False)

    with op.batch_alter_table("live_orders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("live_trading_session_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_live_orders_live_trading_session_id"), ["live_trading_session_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_live_orders_live_trading_session_id_live_trading_sessions",
            "live_trading_sessions",
            ["live_trading_session_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("live_orders", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_live_orders_live_trading_session_id_live_trading_sessions", type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_live_orders_live_trading_session_id"))
        batch_op.drop_column("live_trading_session_id")

    with op.batch_alter_table("live_trades", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_live_trades_session_id"))
    op.drop_table("live_trades")

    with op.batch_alter_table("live_trading_sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_live_trading_sessions_status"))
        batch_op.drop_index(batch_op.f("ix_live_trading_sessions_broker_connection_id"))
        batch_op.drop_index(batch_op.f("ix_live_trading_sessions_strategy_id"))
        batch_op.drop_index(batch_op.f("ix_live_trading_sessions_user_id"))
    op.drop_table("live_trading_sessions")
