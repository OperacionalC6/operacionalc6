import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_admin, require_full_access
from app.db.session import get_db
from app.models.pipeline_run import PipelineRun, PipelineTrigger
from app.models.user import User
from app.services.audit import log_action
from app.services.pipeline import run_pipeline

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
def trigger_pipeline_run(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    background_tasks.add_task(run_pipeline, trigger=PipelineTrigger.MANUAL)

    log_action(
        db,
        action="pipeline_manual_trigger",
        user_id=current_user.id,
        user_email_snapshot=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return {"detail": "Execução do pipeline disparada em segundo plano."}


@router.get("/runs")
def list_pipeline_runs(
    _: User = Depends(require_full_access),
    db: Session = Depends(get_db),
) -> list[dict]:
    runs = db.query(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(50).all()
    return [
        {
            "id": str(r.id),
            "source": r.source,
            "status": r.status.value,
            "trigger": r.trigger.value,
            "records_ingested": r.records_ingested,
            "error_message": r.error_message,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in runs
    ]
