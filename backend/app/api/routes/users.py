from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_admin, require_full_access
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services.audit import log_action

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    current_user: User = Depends(require_full_access),
    db: Session = Depends(get_db),
) -> list[User]:
    return db.query(User).order_by(User.full_name).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        team_id=payload.team_id,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe um usuário com esse e-mail.")
    db.refresh(user)

    log_action(
        db,
        action="user_created",
        user_id=current_user.id,
        user_email_snapshot=current_user.email,
        resource_type="user",
        resource_id=str(user.id),
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        extra={"created_email": user.email, "role": user.role.value},
    )
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    import uuid

    try:
        target = db.get(User, uuid.UUID(user_id))
    except ValueError:
        target = None
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(target, field, value)
    db.add(target)
    db.commit()
    db.refresh(target)

    log_action(
        db,
        action="user_updated",
        user_id=current_user.id,
        user_email_snapshot=current_user.email,
        resource_type="user",
        resource_id=str(target.id),
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        extra={"changes": {k: str(v) for k, v in changes.items()}},
    )
    return target
