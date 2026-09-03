"""
Upload das tabelas de cadastro/config usadas no cálculo de `base_final`
(comissão de GN) — ver skill `project-context`, Fase 1. Cada uma é um
cadastro/referência mantido manualmente pelo usuário fora do Looker, hoje
numa planilha; aqui ele pode reenviar a aba atualizada (CSV ou XLSX) sempre
que precisar, sem depender de mim rodar um script manualmente.

Cada upload SUBSTITUI o conteúdo inteiro da tabela (mesmo padrão de
"apagar e reinserir" do pipeline de métricas) — não é upsert linha a linha.
"""

import io
import logging

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_admin
from app.db.session import get_db
from app.models.alcada_discount_rule import AlcadaDiscountRule
from app.models.commission_rate_tier import CommissionRateTier
from app.models.contract_override import ContractOverride
from app.models.gn_assignment import GnAssignment
from app.models.store_commercial_terms import StoreCommercialTerms
from app.models.store_registry_monthly import StoreRegistryMonthly
from app.models.user import User
from app.services.audit import log_action
from app.services.config_import import (
    import_alcada_discount_rules,
    import_commission_rate_tiers,
    import_contract_overrides,
    import_gn_assignments,
    import_store_commercial_terms,
    import_store_registry_monthly,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config-data", tags=["config-data"])

# chave da URL -> (aba de origem na planilha do usuário, modelo, função de importação)
_TABLES = {
    "store-registry": ("db_carterizacao", StoreRegistryMonthly, import_store_registry_monthly),
    "store-commercial-terms": ("config_carteira", StoreCommercialTerms, import_store_commercial_terms),
    "gn-assignments": ("config_GNs", GnAssignment, import_gn_assignments),
    "commission-rate-tiers": ("config_remuneracao", CommissionRateTier, import_commission_rate_tiers),
    "alcada-discount-rules": ("config_regras_alcada", AlcadaDiscountRule, import_alcada_discount_rules),
    "contract-overrides": ("config_AjustesContrato", ContractOverride, import_contract_overrides),
}


def _read_dataframe(upload: UploadFile, content: bytes, header_row: int) -> pd.DataFrame:
    filename = (upload.filename or "").lower()
    if filename.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content), header=header_row)
    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(content), header=header_row, engine="openpyxl")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Formato não suportado — envie .csv ou .xlsx.",
    )


@router.get("/status")
def config_data_status(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    return [
        {"table": key, "source_sheet": sheet_name, "row_count": db.query(model).count()}
        for key, (sheet_name, model, _import_fn) in _TABLES.items()
    ]


@router.post("/{table}/upload", status_code=status.HTTP_200_OK)
def upload_config_table(
    table: str,
    request: Request,
    file: UploadFile = File(...),
    header_row: int = Query(
        0,
        description=(
            "Linha do cabeçalho real (0 = primeira linha). Use 1 se o arquivo tiver uma "
            "linha de rótulo de grupo acima do cabeçalho de verdade (caso de "
            "db_carterizacao/config_carteira exportadas direto da planilha original)."
        ),
    ),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if table not in _TABLES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tabela '{table}' desconhecida. Opções: {', '.join(_TABLES)}.",
        )

    _sheet_name, _model, import_fn = _TABLES[table]
    content = file.file.read()
    df = _read_dataframe(file, content, header_row)

    count = import_fn(db, df)
    db.commit()

    log_action(
        db,
        action="config_data_upload",
        user_id=current_user.id,
        user_email_snapshot=current_user.email,
        resource_type="config_table",
        resource_id=table,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        extra={"filename": file.filename, "rows_imported": count},
    )
    logger.info("Upload de '%s' concluído: %d registros importados por %s.", table, count, current_user.email)
    return {"table": table, "rows_imported": count}
