"""paleta calida (marca DripGestion) para empresas que nunca cambiaron la paleta azul

Revision ID: d2f6b9a47c13
Revises: c5d8a1f3e2b7
Create Date: 2026-11-19

Las empresas creadas antes de este cambio nacieron con la paleta azul por defecto. Solo se
actualizan las que siguen con TODOS los colores de marca iguales a esos valores: si una
empresa eligio su propio color, no se toca.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd2f6b9a47c13'
down_revision: Union[str, Sequence[str], None] = 'c5d8a1f3e2b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AZUL = {
    "color_primario": "#25A7DA",
    "color_primario_light": "#00ACC1",
    "color_primario_dark": "#0C4A6E",
    "color_background": "#F0FDFA",
    "color_success": "#10b981",
    "color_danger": "#ef4444",
    "color_secondary": "#64748b",
}
CALIDA = {
    "color_primario": "#E86A1F",
    "color_primario_light": "#F5A474",
    "color_primario_dark": "#1C1917",
    "color_background": "#F7F4F0",
    "color_success": "#16a34a",
    "color_danger": "#dc2626",
    "color_secondary": "#78716c",
}


def _cambiar(desde: dict, hacia: dict) -> None:
    tenants = sa.table("tenants", *[sa.column(c, sa.String) for c in desde])
    condicion = sa.and_(*[tenants.c[c] == v for c, v in desde.items()])
    op.execute(tenants.update().where(condicion).values(**hacia))


def upgrade() -> None:
    _cambiar(AZUL, CALIDA)


def downgrade() -> None:
    _cambiar(CALIDA, AZUL)
