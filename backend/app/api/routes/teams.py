from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.team import Team
from app.models.user import User
from app.schemas.team import TeamCreate, TeamOut

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[TeamOut])
def list_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Team]:
    if current_user.role.has_full_access:
        return db.query(Team).order_by(Team.name).all()

    # Usuário 'membro' só enxerga a própria equipe (necessário para a UI de filtro).
    if current_user.team_id is None:
        return []
    team = db.get(Team, current_user.team_id)
    return [team] if team else []


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Team:
    team = Team(name=payload.name, description=payload.description)
    db.add(team)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe uma equipe com esse nome.")
    db.refresh(team)
    return team
