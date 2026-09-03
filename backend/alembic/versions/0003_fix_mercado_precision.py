"""corrige precisão de store_registry_monthly.mercado e
store_commercial_terms.mercado: são R$ (potencial de mercado), não percentual
— Numeric(9,6) estourou com valor real de R$ 40 milhões numa loja

Revision ID: 0003_fix_mercado_precision
Revises: 0002_config_tables
Create Date: 2026-09-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_fix_mercado_precision"
down_revision: Union[str, None] = "0002_config_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "store_registry_monthly",
        "mercado",
        type_=sa.Numeric(18, 2),
        existing_type=sa.Numeric(9, 6),
        existing_nullable=True,
    )
    op.alter_column(
        "store_commercial_terms",
        "mercado",
        type_=sa.Numeric(18, 2),
        existing_type=sa.Numeric(9, 6),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "store_commercial_terms",
        "mercado",
        type_=sa.Numeric(9, 6),
        existing_type=sa.Numeric(18, 2),
        existing_nullable=True,
    )
    op.alter_column(
        "store_registry_monthly",
        "mercado",
        type_=sa.Numeric(9, 6),
        existing_type=sa.Numeric(18, 2),
        existing_nullable=True,
    )
