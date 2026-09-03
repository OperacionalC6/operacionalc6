import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StoreCommercialTerms(Base):
    """
    Identidade e condições comerciais da loja por CNPJ (nome, grupo, % mercado,
    % retorno, % acordo, % comissão seguros).

    Espelha a aba `config_carteira` — cadastro distinto de `store_registry_monthly`
    (aquela é histórico de área/GN por mês; esta é os termos comerciais por
    CNPJ, também versionada por `anomes`, mas mantida/atualizada por eles
    independentemente da carterização). Junções ponto-no-tempo (para um período
    ano/mes) usam a linha de `anomes` mais recente ATÉ aquele período — mais
    correto que a XLOOKUP original da planilha, que pega só a primeira
    ocorrência da coluna sem considerar o período (decisão de modernização,
    documentada aqui em vez de replicar a ambiguidade original).
    """

    __tablename__ = "store_commercial_terms"
    __table_args__ = (UniqueConstraint("cnpj_loja", "anomes", name="uq_store_commercial_terms_cnpj_anomes"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    cnpj_loja: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    anomes: Mapped[str] = mapped_column(String(6), nullable=False, index=True)

    carteira_ajustada: Mapped[str | None] = mapped_column(String(200), nullable=True)
    raiz_cnpj: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cd_loja: Mapped[str | None] = mapped_column(String(30), nullable=True)
    loja: Mapped[str | None] = mapped_column(String(200), nullable=True)
    grupo_loja: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bandeira_principal: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subsegmento: Mapped[str | None] = mapped_column(String(120), nullable=True)
    filial: Mapped[str | None] = mapped_column(String(120), nullable=True)
    regional: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rede: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Mercado é potencial de mercado em R$ (não percentual, ao contrário dos 3 campos
    # abaixo) — chegou a estourar Numeric(9,6) com valor real de R$ 3,3 milhões numa loja.
    mercado: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    retorno: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    acordo: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    comissao_seguros: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    classificacao: Mapped[str | None] = mapped_column(String(60), nullable=True)
    estado: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bairro: Mapped[str | None] = mapped_column(String(120), nullable=True)
    endereco: Mapped[str | None] = mapped_column(String(300), nullable=True)
    loja_nova: Mapped[str | None] = mapped_column(String(10), nullable=True)
    atendimento: Mapped[str | None] = mapped_column(String(60), nullable=True)
    shopping: Mapped[str | None] = mapped_column(String(10), nullable=True)
    concessionaria: Mapped[str | None] = mapped_column(String(10), nullable=True)
    parceiro_atendimento: Mapped[str | None] = mapped_column(String(200), nullable=True)
    master: Mapped[str | None] = mapped_column(String(200), nullable=True)
    retorno_max: Mapped[str | None] = mapped_column(String(30), nullable=True)
    retorno_default: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tipo_limitacao: Mapped[str | None] = mapped_column(String(60), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
