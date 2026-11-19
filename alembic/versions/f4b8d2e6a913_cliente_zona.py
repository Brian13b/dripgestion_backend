"""clientes.zona (zona / barrio para filtrar)

Revision ID: f4b8d2e6a913
Revises: e3a7c5d91b28
Create Date: 2026-11-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f4b8d2e6a913'
down_revision: Union[str, Sequence[str], None] = 'e3a7c5d91b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clientes', sa.Column('zona', sa.String(length=60), nullable=True))
    op.create_index('ix_clientes_zona', 'clientes', ['zona'])


def downgrade() -> None:
    op.drop_index('ix_clientes_zona', table_name='clientes')
    op.drop_column('clientes', 'zona')
