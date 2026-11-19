"""visita_excepcional en movimientos (trazabilidad de visitas fuera de recorrido)

Revision ID: c5d8a1f3e2b7
Revises: b7e24f90c1a5
Create Date: 2026-11-19

Agrega `movimientos.visita_excepcional` (NOT NULL, default false). Los movimientos
existentes quedan como visitas normales.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c5d8a1f3e2b7'
down_revision: Union[str, Sequence[str], None] = 'b7e24f90c1a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'movimientos',
        sa.Column('visita_excepcional', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('movimientos', 'visita_excepcional')
