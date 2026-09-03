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
    # 90 dias, não "date_to" (mesmo dia): métricas de apuração mensal (ex.: comissao_avista)
    # chegam com metric_date = dia 1 do mês da apuração — uma janela de 1 dia só pega dado
    # se "hoje" coincidir exatamente com o dia 1, o que quase nunca acontece.
    date_from = date_from or (date_to - timedelta(days=90))

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

        # Sem isso, cada execução do agendador (3x/dia) empilharia os mesmos registros de
        # novo — não existe upsert por linha (dimensions é JSON livre, não dá pra comparar
        # com segurança). Em vez disso, cada rodada SUBSTITUI a janela que efetivamente
        # buscou. IMPORTANTE: a janela é calculada POR metric_name a partir do que o lote
        # atual realmente trouxe — não usamos [date_from, date_to] (o pedido) como janela de
        # apagar. Descoberto em 2026-09-03, antes de causar perda de dado de verdade: alguns
        # relatórios (ex.: painel_visita_mercado) só conseguem retornar o mês corrente, por
        # causa de um filtro fixo do Looker, mesmo com date_from/date_to pedindo 90 dias —
        # apagar o intervalo pedido inteiro apagaria o mês anterior (que não foi re-buscado
        # agora) assim que o calendário virasse, perdendo aquele dado pra sempre. Substituir
        # só [menor, maior] metric_date que cada metric_name trouxe nesta rodada preserva
        # meses antigos de relatórios "de mês fixo" intactos, e continua substituindo a
        # janela inteira dos relatórios que já retornam o período completo todo run.
        janelas_por_metrica: dict[str, tuple[date, date]] = {}
        for record in raw_records:
            nome = record["metric_name"]
            data_registro = record["metric_date"]
            minimo, maximo = janelas_por_metrica.get(nome, (data_registro, data_registro))
            janelas_por_metrica[nome] = (min(minimo, data_registro), max(maximo, data_registro))

        deleted = 0
        for nome, (minimo, maximo) in janelas_por_metrica.items():
            deleted += (
                db.query(Metric)
                .filter(
                    Metric.source == connector.source_name,
                    Metric.metric_name == nome,
                    Metric.metric_date >= minimo,
                    Metric.metric_date <= maximo,
                )
                .delete(synchronize_session=False)
            )
        if deleted:
            logger.info(
                "Removidos %d registros antigos de '%s' (janela calculada por métrica) antes de reinserir.",
                deleted,
                connector.source_name,
            )

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
