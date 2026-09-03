"""tabelas de cadastro/config: store_registry_monthly, store_commercial_terms,
gn_assignments, commission_rate_tiers, alcada_discount_rules, contract_overrides

Revision ID: 0002_config_tables
Revises: 0001_init
Create Date: 2026-09-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_config_tables"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "store_registry_monthly",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ano", sa.Integer, nullable=False),
        sa.Column("mes", sa.Integer, nullable=False),
        sa.Column("anomes", sa.String(6), nullable=False),
        sa.Column("chave_loja", sa.String(120), nullable=False),
        sa.Column("cnpj_loja", sa.String(20), nullable=True),
        sa.Column("carterizacao_ehs", sa.String(120), nullable=True),
        sa.Column("cd_loja", sa.String(30), nullable=True),
        sa.Column("loja", sa.String(200), nullable=True),
        sa.Column("loja_nova", sa.String(10), nullable=True),
        sa.Column("cidade", sa.String(120), nullable=True),
        sa.Column("rede", sa.String(120), nullable=True),
        sa.Column("regional", sa.String(60), nullable=True),
        sa.Column("filial", sa.String(120), nullable=True),
        sa.Column("gp", sa.String(120), nullable=True),
        sa.Column("gn", sa.String(120), nullable=True),
        sa.Column("gn_backup", sa.String(120), nullable=True),
        sa.Column("atendimento", sa.String(60), nullable=True),
        sa.Column("classificacao", sa.String(60), nullable=True),
        sa.Column("shopping", sa.String(10), nullable=True),
        sa.Column("concessionaria", sa.String(10), nullable=True),
        sa.Column("mercado", sa.Numeric(9, 6), nullable=True),
        sa.Column("retorno", sa.Numeric(9, 6), nullable=True),
        sa.Column("acordo", sa.Numeric(9, 6), nullable=True),
        sa.Column("comissao_seguros", sa.Numeric(9, 6), nullable=True),
        sa.Column("parceiro_atendimento", sa.String(200), nullable=True),
        sa.Column("master", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("chave_loja", "ano", "mes", name="uq_store_registry_chave_ano_mes"),
    )
    op.create_index("ix_store_registry_monthly_ano", "store_registry_monthly", ["ano"])
    op.create_index("ix_store_registry_monthly_mes", "store_registry_monthly", ["mes"])
    op.create_index("ix_store_registry_monthly_anomes", "store_registry_monthly", ["anomes"])
    op.create_index("ix_store_registry_monthly_chave_loja", "store_registry_monthly", ["chave_loja"])
    op.create_index("ix_store_registry_monthly_cnpj_loja", "store_registry_monthly", ["cnpj_loja"])

    op.create_table(
        "store_commercial_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cnpj_loja", sa.String(20), nullable=False),
        sa.Column("anomes", sa.String(6), nullable=False),
        sa.Column("carteira_ajustada", sa.String(200), nullable=True),
        sa.Column("raiz_cnpj", sa.String(20), nullable=True),
        sa.Column("cd_loja", sa.String(30), nullable=True),
        sa.Column("loja", sa.String(200), nullable=True),
        sa.Column("grupo_loja", sa.String(120), nullable=True),
        sa.Column("bandeira_principal", sa.String(120), nullable=True),
        sa.Column("subsegmento", sa.String(120), nullable=True),
        sa.Column("filial", sa.String(120), nullable=True),
        sa.Column("regional", sa.String(60), nullable=True),
        sa.Column("rede", sa.String(120), nullable=True),
        sa.Column("mercado", sa.Numeric(9, 6), nullable=True),
        sa.Column("retorno", sa.Numeric(9, 6), nullable=True),
        sa.Column("acordo", sa.Numeric(9, 6), nullable=True),
        sa.Column("comissao_seguros", sa.Numeric(9, 6), nullable=True),
        sa.Column("classificacao", sa.String(60), nullable=True),
        sa.Column("estado", sa.String(10), nullable=True),
        sa.Column("cidade", sa.String(120), nullable=True),
        sa.Column("bairro", sa.String(120), nullable=True),
        sa.Column("endereco", sa.String(300), nullable=True),
        sa.Column("loja_nova", sa.String(10), nullable=True),
        sa.Column("atendimento", sa.String(60), nullable=True),
        sa.Column("shopping", sa.String(10), nullable=True),
        sa.Column("concessionaria", sa.String(10), nullable=True),
        sa.Column("parceiro_atendimento", sa.String(200), nullable=True),
        sa.Column("master", sa.String(200), nullable=True),
        sa.Column("retorno_max", sa.String(30), nullable=True),
        sa.Column("retorno_default", sa.String(30), nullable=True),
        sa.Column("tipo_limitacao", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("cnpj_loja", "anomes", name="uq_store_commercial_terms_cnpj_anomes"),
    )
    op.create_index("ix_store_commercial_terms_cnpj_loja", "store_commercial_terms", ["cnpj_loja"])
    op.create_index("ix_store_commercial_terms_anomes", "store_commercial_terms", ["anomes"])

    op.create_table(
        "gn_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("area", sa.String(200), nullable=False),
        sa.Column("ano", sa.Integer, nullable=False),
        sa.Column("mes", sa.Integer, nullable=False),
        sa.Column("gn_responsavel", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("area", "ano", "mes", name="uq_gn_assignments_area_ano_mes"),
    )
    op.create_index("ix_gn_assignments_area", "gn_assignments", ["area"])
    op.create_index("ix_gn_assignments_ano", "gn_assignments", ["ano"])
    op.create_index("ix_gn_assignments_mes", "gn_assignments", ["mes"])

    op.create_table(
        "commission_rate_tiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("produto", sa.String(120), nullable=False),
        sa.Column("ano", sa.Integer, nullable=False),
        sa.Column("mes", sa.Integer, nullable=False),
        sa.Column("comissao_abaixo_100", sa.Numeric(9, 6), nullable=False),
        sa.Column("comissao_100_119", sa.Numeric(9, 6), nullable=False),
        sa.Column("comissao_acima_120", sa.Numeric(9, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("produto", "ano", "mes", name="uq_commission_rate_tiers_produto_ano_mes"),
    )
    op.create_index("ix_commission_rate_tiers_produto", "commission_rate_tiers", ["produto"])
    op.create_index("ix_commission_rate_tiers_ano", "commission_rate_tiers", ["ano"])
    op.create_index("ix_commission_rate_tiers_mes", "commission_rate_tiers", ["mes"])

    op.create_table(
        "alcada_discount_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("alcada", sa.String(120), nullable=False),
        sa.Column("desconto", sa.Numeric(9, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("alcada", name="uq_alcada_discount_rules_alcada"),
    )
    op.create_index("ix_alcada_discount_rules_alcada", "alcada_discount_rules", ["alcada"])

    op.create_table(
        "contract_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("codigo_contrato", sa.String(60), nullable=False),
        sa.Column("filial_ajustada", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("codigo_contrato", name="uq_contract_overrides_codigo_contrato"),
    )
    op.create_index("ix_contract_overrides_codigo_contrato", "contract_overrides", ["codigo_contrato"])


def downgrade() -> None:
    op.drop_index("ix_contract_overrides_codigo_contrato", table_name="contract_overrides")
    op.drop_table("contract_overrides")

    op.drop_index("ix_alcada_discount_rules_alcada", table_name="alcada_discount_rules")
    op.drop_table("alcada_discount_rules")

    op.drop_index("ix_commission_rate_tiers_mes", table_name="commission_rate_tiers")
    op.drop_index("ix_commission_rate_tiers_ano", table_name="commission_rate_tiers")
    op.drop_index("ix_commission_rate_tiers_produto", table_name="commission_rate_tiers")
    op.drop_table("commission_rate_tiers")

    op.drop_index("ix_gn_assignments_mes", table_name="gn_assignments")
    op.drop_index("ix_gn_assignments_ano", table_name="gn_assignments")
    op.drop_index("ix_gn_assignments_area", table_name="gn_assignments")
    op.drop_table("gn_assignments")

    op.drop_index("ix_store_commercial_terms_anomes", table_name="store_commercial_terms")
    op.drop_index("ix_store_commercial_terms_cnpj_loja", table_name="store_commercial_terms")
    op.drop_table("store_commercial_terms")

    op.drop_index("ix_store_registry_monthly_cnpj_loja", table_name="store_registry_monthly")
    op.drop_index("ix_store_registry_monthly_chave_loja", table_name="store_registry_monthly")
    op.drop_index("ix_store_registry_monthly_anomes", table_name="store_registry_monthly")
    op.drop_index("ix_store_registry_monthly_mes", table_name="store_registry_monthly")
    op.drop_index("ix_store_registry_monthly_ano", table_name="store_registry_monthly")
    op.drop_table("store_registry_monthly")
