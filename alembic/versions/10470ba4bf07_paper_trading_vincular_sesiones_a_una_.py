"""paper trading: vincular sesiones a una estrategia guardada

Revision ID: 10470ba4bf07
Revises: d3464c20a891
Create Date: 2026-07-25 22:04:19.977654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10470ba4bf07'
down_revision: Union[str, Sequence[str], None] = 'd3464c20a891'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("paper_trading_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("strategy_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_paper_trading_sessions_strategy_id"), ["strategy_id"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_paper_trading_sessions_strategy_id_saved_strategies",
            "saved_strategies",
            ["strategy_id"],
            ["id"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("paper_trading_sessions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_paper_trading_sessions_strategy_id_saved_strategies", type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_paper_trading_sessions_strategy_id"))
        batch_op.drop_column("strategy_id")
