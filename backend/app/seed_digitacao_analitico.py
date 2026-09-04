"""
Carga histórica única de `digitacao_analitico` a partir da planilha do
usuário (aba `db_pagasanalitico` de Construcao.xlsx) — usada porque o export
do Looker desse relatório específico tem um limite de ~500 linhas por
download (confirmado pelo usuário, 2026-09-04), inviabilizando puxar meses
de histórico via RPA (ver skill `rpa-conventions`, item 26). A partir do
primeiro dia não coberto por essa carga, o RPA (janela curta, "3 day")
assume sozinho — sem sobreposição de responsabilidade, cada um cobre um
pedaço da linha do tempo.

Reaproveita o parsing REAL do RPA (`PortalRpaConnector._parse_report` + o
`column_mapping` já validado em `portal_selectors.json`) em vez de duplicar
a lógica de mapeamento — a aba `db_pagasanalitico` da planilha tem as
MESMAS colunas do CSV/XLSX que o Looker exporta.

Aponta direto para o `Construcao.xlsx` original (várias abas) — passa
sheet_name="db_pagasanalitico" para o `_parse_report`, não precisa extrair
a aba antes.

Substitui (não empilha) qualquer registro já existente na janela
[date_from, date_to] antes de inserir — mesmo padrão idempotente do
`run_pipeline` — seguro rodar mais de uma vez.

Executar com:
    python -m app.seed_digitacao_analitico /caminho/arquivo.xlsx 2026-01-01 2026-08-31
"""

import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.models.metric import Metric
from app.services.connectors.portal_rpa import PortalRpaConnector

configure_logging()
logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "services" / "connectors" / "portal_selectors.json"


def _load_column_mapping() -> dict:
    cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    for report in cfg["looker"]["reports"]:
        if report["name"] != "acompanhamento_veiculos":
            continue
        for tile in report["tiles"]:
            if tile["key"] == "analitico":
                return tile["column_mapping"]
    raise RuntimeError("column_mapping de acompanhamento_veiculos/analitico não encontrado em portal_selectors.json.")


def seed_digitacao_analitico(xlsx_path: str, date_from: date, date_to: date) -> None:
    mapping = _load_column_mapping()
    records = PortalRpaConnector._parse_report(
        Path(xlsx_path),
        {"column_mapping": mapping},
        date_from,
        date_to,
        sheet_name="db_pagasanalitico",
    )
    logger.info("Parseados %d registros de '%s' (%s a %s).", len(records), xlsx_path, date_from, date_to)

    db = SessionLocal()
    try:
        deleted = (
            db.query(Metric)
            .filter(
                Metric.source == "portal_rpa",
                Metric.metric_name == "digitacao_analitico",
                Metric.metric_date >= date_from,
                Metric.metric_date <= date_to,
            )
            .delete(synchronize_session=False)
        )
        if deleted:
            logger.info(
                "Removidos %d registros antigos de 'digitacao_analitico' na janela %s–%s antes de reinserir.",
                deleted,
                date_from,
                date_to,
            )

        for record in records:
            db.add(
                Metric(
                    metric_date=record["metric_date"],
                    metric_name=record["metric_name"],
                    value=record["value"],
                    dimensions=record.get("dimensions"),
                    source="portal_rpa",
                )
            )
        db.commit()
        logger.info("Carga concluída: %d registros de 'digitacao_analitico' gravados.", len(records))
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Uso: python -m app.seed_digitacao_analitico /caminho/arquivo.xlsx AAAA-MM-DD AAAA-MM-DD",
            file=sys.stderr,
        )
        sys.exit(1)
    xlsx_path, date_from_str, date_to_str = sys.argv[1:4]
    seed_digitacao_analitico(
        xlsx_path,
        datetime.strptime(date_from_str, "%Y-%m-%d").date(),
        datetime.strptime(date_to_str, "%Y-%m-%d").date(),
    )
