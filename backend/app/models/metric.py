import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Metric(Base):
    """
    Tabela fato genérica dos relatórios operacionais extraídos do C6.

    Modelada de forma flexível (metric_name + dimensions em JSONB) porque a
    estrutura exata dos relatórios do WebAutorizador/API Corban ainda não foi
    definida com o time. Uma vez mapeados os relatórios reais, considere criar
    tabelas fato dedicadas (ex: "propostas", "producao_diaria") para
    performance/consultas mais ricas — esta tabela cobre o caso genérico.
    """

    __tablename__ = "metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True
    )

    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    dimensions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    source: Mapped[str] = mapped_column(String(50), nullable=False)  # "api_corban" | "portal_rpa"
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_runs.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
