"""username unico por empresa (BUG-10)

Revision ID: a3c91e2d7b10
Revises: fd34ef855ee7
Create Date: 2026-11-19

Antes `users.username` era único en TODA la base: el mismo teléfono no podía ser
cliente en dos distribuidoras. Ahora es único por empresa (tenant_id, username) y,
para los superadmin (tenant_id NULL), mediante un índice parcial.

Antes de aplicar en producción: `SELECT tenant_id, username, count(*) FROM users
GROUP BY 1, 2 HAVING count(*) > 1;` debe devolver 0 filas (hoy no puede haber
duplicados porque el índice anterior era único global).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a3c91e2d7b10'
down_revision: Union[str, Sequence[str], None] = 'fd34ef855ee7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_users_username', table_name='users')
    op.create_index('ix_users_username', 'users', ['username'], unique=False)
    op.create_unique_constraint('uq_users_tenant_username', 'users', ['tenant_id', 'username'])
    op.create_index(
        'uq_users_superadmin_username',
        'users',
        ['username'],
        unique=True,
        postgresql_where=sa.text('tenant_id IS NULL'),
    )


def downgrade() -> None:
    # Solo es posible si no hay usernames repetidos entre empresas.
    op.drop_index('uq_users_superadmin_username', table_name='users')
    op.drop_constraint('uq_users_tenant_username', 'users', type_='unique')
    op.drop_index('ix_users_username', table_name='users')
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
