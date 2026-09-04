"""
Lógica compartilhada pelas cargas históricas de um `metric_name` específico a
partir de uma aba do `Construcao.xlsx` do usuário — usada quando o Looker
limita o export daquele relatório a ~500 linhas, inviabilizando puxar meses de
histórico via RPA (ver skill `rpa-conventions`, item 26).

Cada carga reaproveita o MESMO parsing do RPA real
(`PortalRpaConnector._parse_report` + o `column_mapping` já validado em
`portal_selectors.json`) contra a aba correspondente da planilha, em vez de
duplicar a lógica de mapeamento — as abas `db_*` da planilha têm as MESMAS
colunas dos CSV/XLSX que o Looker exporta.

Substitui (não empilha) qualquer registro já existente na janela
[date_from, date_to] antes de inserir — mesmo padrão idempotente do
`run_pipeline` — seguro rodar mais de uma vez.
"""

import json
import logging
from datetime import date
from pathlib import Path

from app.db.session import SessionLocal
from app.models.metric import Metric
from app.services.connectors.portal_rpa import PortalRpaConnector

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent / "connectors" / "portal_selectors.json"


def _load_column_mapping(report_name: str, tile_key: str, metric_name: str) -> dict:
    cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    for report in cfg["looker"]["reports"]:
        if report["name"] != report_name:
            continue
        for tile in report["tiles"]:
            if tile["key"] != tile_key:
                continue
            mapping_cfg = tile.get("column_mapping")
            mappings = mapping_cfg if isinstance(mapping_cfg, list) else [mapping_cfg]
            for mapping in mappings:
                if mapping and mapping.get("metric_name") == metric_name:
                    return mapping
    raise RuntimeError(
        f"column_mapping de {report_name}/{tile_key} (metric_name='{metric_name}') "
        "não encontrado em portal_selectors.json."
    )


def seed_from_spreadsheet(
    *,
    report_name: str,
    tile_key: str,
    metric_name: str,
    sheet_name: str,
    xlsx_path: str,
    date_from: date,
    date_to: date,
) -> None:
    mapping = _load_column_mapping(report_name, tile_key, metric_name)
    records = PortalRpaConnector._parse_report(
        Path(xlsx_path), {"column_mapping": mapping}, date_from, date_to, sheet_name=sheet_name
    )
    logger.info(
        "Parseados %d registros de '%s' (aba '%s', %s a %s).",
        len(records),
        xlsx_path,
        sheet_name,
        date_from,
        date_to,
    )

    db = SessionLocal()
    try:
        deleted = (
            db.query(Metric)
            .filter(
                Metric.source == "portal_rpa",
                Metric.metric_name == metric_name,
                Metric.metric_date >= date_from,
                Metric.metric_date <= date_to,
            )
            .delete(synchronize_session=False)
        )
        if deleted:
            logger.info(
                "Removidos %d registros antigos de '%s' na janela %s–%s antes de reinserir.",
                deleted,
                metric_name,
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
        logger.info("Carga concluída: %d registros de '%s' gravados.", len(records), metric_name)
    finally:
        db.close()
