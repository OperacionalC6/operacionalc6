"""
Carga inicial das tabelas de cadastro/config (Fase 1 do dashboard de comissão
de GN — ver skill `project-context`) a partir da planilha "Construcao.xlsx"
que o usuário mantém manualmente.

Diferente de `app/seed.py` (que roda em todo start do container), este script
é executado manualmente, uma vez, sob demanda — não faz parte do
`entrypoint.sh`. Reexecutar é seguro (cada tabela é substituída por inteiro,
mesmo padrão de `run_pipeline`), então também serve pra recarregar depois de
uma atualização manual da planilha até o endpoint de upload (Fase 1, ainda
não construído) existir.

Duas abas (`db_carterizacao`, `config_carteira`) têm cabeçalho em DUAS linhas
no Excel (linha 1 é um rótulo de grupo repetido, ex. "CARTEIRA" — a real vem
na linha 2); as demais têm cabeçalho normal na linha 1.

Executar com: python -m app.seed_config /caminho/para/Construcao.xlsx
"""

import logging
import sys

import pandas as pd

from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.config_import import (
    import_alcada_discount_rules,
    import_commission_rate_tiers,
    import_contract_overrides,
    import_gn_assignments,
    import_store_commercial_terms,
    import_store_registry_monthly,
)

configure_logging()
logger = logging.getLogger(__name__)

# (nome da aba, linha do cabeçalho real (0-based), função de importação)
_SHEETS: list[tuple[str, int, callable]] = [
    ("db_carterizacao", 1, import_store_registry_monthly),
    ("config_carteira", 1, import_store_commercial_terms),
    ("config_GNs", 0, import_gn_assignments),
    ("config_remuneracao", 0, import_commission_rate_tiers),
    ("config_regras_alcada", 0, import_alcada_discount_rules),
    ("config_AjustesContrato", 0, import_contract_overrides),
]


def seed_config(xlsx_path: str) -> None:
    db = SessionLocal()
    try:
        for sheet_name, header_row, import_fn in _SHEETS:
            df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=header_row, engine="openpyxl")
            count = import_fn(db, df)
            db.commit()
            logger.info("Aba '%s': %d registros importados para %s.", sheet_name, count, import_fn.__name__)
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python -m app.seed_config /caminho/para/Construcao.xlsx", file=sys.stderr)
        sys.exit(1)
    seed_config(sys.argv[1])
