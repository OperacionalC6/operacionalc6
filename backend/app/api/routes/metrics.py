from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user
from app.db.session import get_db
from app.models.metric import Metric
from app.models.user import User
from app.schemas.metric import MetricOut
from app.services.audit import log_action

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=list[MetricOut])
def list_metrics(
    request: Request,
    # 90 dias (não 30): métricas de apuração mensal (ex.: comissao_avista) chegam com
    # metric_date = dia 1 do mês da apuração — uma janela de 30 dias corta o mês
    # corrente inteiro sempre que "hoje" cai nos primeiros dias do mês seguinte.
    date_from: date = Query(default_factory=lambda: date.today() - timedelta(days=90)),
    date_to: date = Query(default_factory=date.today),
    metric_name: str | None = None,
    team_id: str | None = Query(default=None, description="Somente respeitado para admin/gestor."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Metric]:
    query = db.query(Metric).filter(Metric.metric_date >= date_from, Metric.metric_date <= date_to)

    if metric_name:
        query = query.filter(Metric.metric_name == metric_name)

    if current_user.role.has_full_access:
        if team_id:
            import uuid

            try:
                query = query.filter(Metric.team_id == uuid.UUID(team_id))
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id inválido.")
    else:
        # Usuário 'membro': escopo forçado à própria equipe, mesmo que tente enviar team_id.
        if current_user.team_id is None:
            return []
        query = query.filter(Metric.team_id == current_user.team_id)
        if team_id and str(current_user.team_id) != team_id:
            log_action(
                db,
                action="metrics_scope_violation_attempt",
                user_id=current_user.id,
                user_email_snapshot=current_user.email,
                resource_type="metrics",
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                extra={"requested_team_id": team_id, "own_team_id": str(current_user.team_id)},
            )

    results = query.order_by(Metric.metric_date.desc()).limit(5000).all()

    log_action(
        db,
        action="metrics_read",
        user_id=current_user.id,
        user_email_snapshot=current_user.email,
        resource_type="metrics",
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        extra={
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "metric_name": metric_name,
            "result_count": len(results),
        },
    )
    return results
