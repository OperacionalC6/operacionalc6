import re
from abc import ABC, abstractmethod
from datetime import date
from typing import TypedDict

# Colunas monetárias/numéricas dos exports Looker vêm formatadas como texto, ex.:
# 'R$ 653,440.00' (vírgula de milhar, ponto decimal — não é o formato BR
# tradicional, é o locale do Looker). Alguns relatórios também abreviam números
# grandes em vez de escrever por extenso — descoberto em teste real 2026-09-03
# (painel_visita_mercado): "151.9 mil" (×1.000), "1.6 MM" (×1.000.000).
# Compartilhado entre o parsing do RPA (colunas promovidas a `value`) e qualquer
# leitura posterior de uma coluna numérica que ficou só como dimensão (JSONB) —
# o mesmo texto bruto do Looker aparece nos dois lugares.
_ABREVIACAO_RE = re.compile(r"^(-?[\d.]+)\s*(mil|mm|mi)$", re.IGNORECASE)
_MULTIPLICADOR_POR_SUFIXO = {"mil": 1_000, "mm": 1_000_000, "mi": 1_000_000}


def parse_looker_number(raw: object) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    cleaned = str(raw).replace("R$", "").strip()
    match = _ABREVIACAO_RE.match(cleaned)
    if match:
        numero, sufixo = match.groups()
        return float(numero) * _MULTIPLICADOR_POR_SUFIXO[sufixo.lower()]
    return float(cleaned.replace(",", ""))


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
