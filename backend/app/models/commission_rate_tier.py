import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CommissionRateTier(Base):
    """
    Tabela de % de comissão do GN por produto, em 3 faixas de atingimento de
    meta (<100%, 100-119%, >=120%).

    Espelha a aba `config_remuneracao` — política de remuneração interna,
    pode mudar mês a mês.
    """

    __tablename__ = "commission_rate_tiers"
    __table_args__ = (UniqueConstraint("produto", "ano", "mes", name="uq_commission_rate_tiers_produto_ano_mes"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    produto: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    ano: Mapped[int] = mapped_column(nullable=False, index=True)
    mes: Mapped[int] = mapped_column(nullable=False, index=True)
    comissao_abaixo_100: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    comissao_100_119: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    comissao_acima_120: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
