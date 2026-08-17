import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.models.pipeline_run import PipelineTrigger
from app.services.pipeline import run_pipeline

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = BackgroundScheduler(timezone=settings.pipeline_timezone)

    for time_str in settings.pipeline_schedule_list:
        try:
            hour, minute = time_str.split(":")
        except ValueError:
            logger.warning("Horário inválido em PIPELINE_CRON_SCHEDULES: '%s' (ignorado)", time_str)
            continue

        scheduler.add_job(
            run_pipeline,
            trigger=CronTrigger(hour=int(hour), minute=int(minute), timezone=settings.pipeline_timezone),
            kwargs={"trigger": PipelineTrigger.SCHEDULE},
            id=f"pipeline_{time_str.replace(':', '')}",
            replace_existing=True,
            misfire_grace_time=60 * 30,
        )
        logger.info("Job de pipeline agendado para %s (%s)", time_str, settings.pipeline_timezone)

    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
