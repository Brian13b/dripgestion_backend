"""calendario operativo: turnos de recorrido con 1 a 3 repartidores

Revision ID: e3a7c5d91b28
Revises: d2f6b9a47c13
Create Date: 2026-11-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e3a7c5d91b28'
down_revision: Union[str, Sequence[str], None] = 'd2f6b9a47c13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'turnos_recorrido',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('recorrido_id', sa.Integer(), sa.ForeignKey('recorridos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('hora_desde', sa.Time(), nullable=False),
        sa.Column('hora_hasta', sa.Time(), nullable=False),
        sa.Column('nota', sa.String(length=200), nullable=True),
        sa.UniqueConstraint('tenant_id', 'recorrido_id', 'fecha', name='uq_turno_recorrido_fecha'),
    )
    op.create_index('ix_turnos_recorrido_id', 'turnos_recorrido', ['id'])
    op.create_index('ix_turnos_recorrido_tenant_id', 'turnos_recorrido', ['tenant_id'])
    op.create_index('ix_turnos_recorrido_recorrido_id', 'turnos_recorrido', ['recorrido_id'])
    op.create_index('ix_turnos_recorrido_fecha', 'turnos_recorrido', ['fecha'])

    rol = sa.Enum('CONDUCTOR', 'AYUDANTE', name='rolturno')
    op.create_table(
        'turnos_repartidores',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('turno_id', sa.Integer(), sa.ForeignKey('turnos_recorrido.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('rol', rol, nullable=False),
        sa.UniqueConstraint('turno_id', 'user_id', name='uq_turno_repartidor'),
    )
    op.create_index('ix_turnos_repartidores_turno_id', 'turnos_repartidores', ['turno_id'])
    op.create_index('ix_turnos_repartidores_user_id', 'turnos_repartidores', ['user_id'])


def downgrade() -> None:
    op.drop_table('turnos_repartidores')
    op.drop_table('turnos_recorrido')
    sa.Enum(name='rolturno').drop(op.get_bind(), checkfirst=True)
