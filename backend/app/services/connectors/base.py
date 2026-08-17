from abc import ABC, abstractmethod
from datetime import date
from typing import TypedDict


class ConnectorRecord(TypedDict):
    """Um registro normalizado, pronto para virar uma linha na tabela `metrics`."""

    team_name: str | None  # nome da área/equipe; None = métrica não segmentada por equipe
    metric_date: date
    metric_name: str
    value: float
    dimensions: dict | None


class DataConnector(ABC):
    """
    Interface comum para qualquer fonte de dados do C6 (API oficial ou RPA de
    portal). O pipeline (app/services/pipeline.py) não sabe nem se importa
    qual implementação está por trás — isso permite trocar de RPA para API
    oficial assim que a homologação sair, sem tocar no resto do sistema.
    """

    source_name: str

    @abstractmethod
    def fetch(self, *, date_from: date, date_to: date) -> list[ConnectorRecord]:
        """Busca e retorna os registros normalizados do período solicitado."""
        raise NotImplementedError
