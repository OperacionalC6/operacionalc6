from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.base_final import get_base_final_rows
from app.services.gn_dashboard import get_area_scorecard, list_areas

router = APIRouter(prefix="/gn-dashboard", tags=["gn-dashboard"])


@router.get("/areas")
def list_areas_route(
    ano: int = Query(...),
    mes: int = Query(..., ge=1, le=12),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    return list_areas(db, ano=ano, mes=mes)


@router.get("/area-scorecard")
def area_scorecard_route(
    area: str = Query(...),
    ano: int = Query(...),
    mes: int = Query(..., ge=1, le=12),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = get_area_scorecard(db, area=area, ano=ano, mes=mes)
    if not result["lojas"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhuma loja cadastrada para a área '{area}' em {ano}-{mes:02d}.",
        )
    return result


@router.get("/base-final")
def base_final_route(
    ano: int = Query(...),
    mes: int = Query(..., ge=1, le=12),
    area: str | None = Query(
        None, description="Filtra por AREA_LOJA_EHS. Omitido: todos os contratos do mês."
    ),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = get_base_final_rows(db, ano=ano, mes=mes)
    if area:
        rows = [r for r in rows if r["area_loja_ehs"] == area]
    return rows
