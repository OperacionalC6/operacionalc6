import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.metric import Metric
from app.models.pipeline_run import PipelineRun, PipelineStatus, PipelineTrigger
from app.models.team import Team
from app.services.connectors import get_connector

logger = logging.getLogger(__name__)
settings = get_settings()


def run_pipeline(
    *,
    trigger: PipelineTrigger = PipelineTrigger.SCHEDULE,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PipelineRun:
    """
    Executa uma rodada completa de ingestão: busca dados na fonte configurada
    (API Corban ou RPA de portal), normaliza e grava em `metrics`, registrando
    o resultado em `pipeline_runs` para auditoria/observabilidade.

    Abre sua própria sessão de banco porque é chamado tanto pelo agendador
    (fora do ciclo de request/response) quanto por um endpoint manual.
    """
    db: Session = SessionLocal()
    date_to = date_to or date.today()
    date_from = date_from or date_to

    run = PipelineRun(
        source=settings.data_source_mode,
        status=PipelineStatus.RUNNING,
        trigger=trigger,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        connector = get_connector()
        raw_records = connector.fetch(date_from=date_from, date_to=date_to)

        team_cache: dict[str, Team | None] = {}
        inserted = 0

        for record in raw_records:
            team_id = None
            team_name = record.get("team_name")
            if team_name:
                if team_name not in team_cache:
                    team_cache[team_name] = db.query(Team).filter(Team.name == team_name).first()
                team = team_cache[team_name]
                if team is None:
                    logger.warning(
                        "Equipe '%s' retornada pela fonte de dados não existe em `teams`; "
                        "métrica será gravada sem team_id. Cadastre a equipe para segmentar.",
                        team_name,
                    )
                else:
                    team_id = team.id

            db.add(
                Metric(
                    team_id=team_id,
                    metric_date=record["metric_date"],
                    metric_name=record["metric_name"],
                    value=record["value"],
                    dimensions=record.get("dimensions"),
                    source=connector.source_name,
                    pipeline_run_id=run.id,
                )
            )
            inserted += 1

        run.status = PipelineStatus.SUCCESS
        run.records_ingested = inserted
        db.add(run)
        db.commit()
        logger.info("Pipeline concluído: %d registros ingeridos (fonte=%s).", inserted, connector.source_name)

    except Exception as exc:  # noqa: BLE001 — precisamos capturar qualquer falha para registrar no PipelineRun
        db.rollback()
        run.status = PipelineStatus.FAILED
        run.error_message = str(exc)[:2000]
        db.add(run)
        db.commit()
        logger.exception("Pipeline falhou.")
    finally:
        from datetime import datetime, timezone

        run.finished_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        db.close()

    return run
