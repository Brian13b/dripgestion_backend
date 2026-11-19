"""idempotency_key en movimientos (idempotencia de entregas y pagos)

Revision ID: b7e24f90c1a5
Revises: a3c91e2d7b10
Create Date: 2026-11-19

Agrega `movimientos.idempotency_key` (nullable) y una restricción única
(tenant_id, idempotency_key). En PostgreSQL los NULL no chocan entre sí, así que los
movimientos existentes y los de clientes que no envían la clave no se ven afectados.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b7e24f90c1a5'
down_revision: Union[str, Sequence[str], None] = 'a3c91e2d7b10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('movimientos', sa.Column('idempotency_key', sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        'uq_movimientos_tenant_idempotency', 'movimientos', ['tenant_id', 'idempotency_key']
    )


def downgrade() -> None:
    op.drop_constraint('uq_movimientos_tenant_idempotency', 'movimientos', type_='unique')
    op.drop_column('movimientos', 'idempotency_key')
