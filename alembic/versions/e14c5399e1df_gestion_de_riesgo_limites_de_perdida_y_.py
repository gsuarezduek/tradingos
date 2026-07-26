"""gestion de riesgo: limites de perdida y motivo de pausa

Revision ID: e14c5399e1df
Revises: f382091a6bf4
Create Date: 2026-07-26 10:34:36.991190

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e14c5399e1df'
down_revision: Union[str, Sequence[str], None] = 'f382091a6bf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("daily_loss_limit_usdt", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("weekly_loss_limit_usdt", sa.Float(), nullable=True))

    with op.batch_alter_table("live_trading_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("paused_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("live_trading_sessions", schema=None) as batch_op:
        batch_op.drop_column("paused_reason")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("weekly_loss_limit_usdt")
        batch_op.drop_column("daily_loss_limit_usdt")
