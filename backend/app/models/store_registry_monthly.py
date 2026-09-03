import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StoreRegistryMonthly(Base):
    """
    Cadastro histórico (mês a mês) de qual área/GN/GP cada loja pertence.

    Espelha a aba `db_carterizacao` da planilha de construção do usuário — não é
    dado do Looker, é mantido manualmente por eles e muda com reorganizações
    internas. Guardamos histórico completo (uma linha por loja por mês) porque
    a fonte já vem assim; junções ponto-no-tempo (mês da apuração) usam o par
    (ano, mes) exato, não "o mais recente".
    """

    __tablename__ = "store_registry_monthly"
    __table_args__ = (UniqueConstraint("chave_loja", "ano", "mes", name="uq_store_registry_chave_ano_mes"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    ano: Mapped[int] = mapped_column(nullable=False, index=True)
    mes: Mapped[int] = mapped_column(nullable=False, index=True)
    anomes: Mapped[str] = mapped_column(String(6), nullable=False, index=True)
    chave_loja: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    cnpj_loja: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    carterizacao_ehs: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cd_loja: Mapped[str | None] = mapped_column(String(30), nullable=True)
    loja: Mapped[str | None] = mapped_column(String(200), nullable=True)
    loja_nova: Mapped[str | None] = mapped_column(String(10), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    rede: Mapped[str | None] = mapped_column(String(120), nullable=True)
    regional: Mapped[str | None] = mapped_column(String(60), nullable=True)
    filial: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gp: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gn: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gn_backup: Mapped[str | None] = mapped_column(String(120), nullable=True)
    atendimento: Mapped[str | None] = mapped_column(String(60), nullable=True)
    classificacao: Mapped[str | None] = mapped_column(String(60), nullable=True)
    shopping: Mapped[str | None] = mapped_column(String(10), nullable=True)
    concessionaria: Mapped[str | None] = mapped_column(String(10), nullable=True)
    mercado: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    retorno: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    acordo: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    comissao_seguros: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    parceiro_atendimento: Mapped[str | None] = mapped_column(String(200), nullable=True)
    master: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
