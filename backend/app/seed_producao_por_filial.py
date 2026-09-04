"""
Carga histórica única de `producao_por_filial` a partir da planilha do
usuário (aba `db_Metas` de Construcao.xlsx) — mesma razão e mesmo padrão de
`seed_digitacao_analitico.py` (ver docstring lá, e skill `rpa-conventions`
item 26).

`producao_por_filial` é usado por `base_final` só pra ler o FATOR_META
(dimensão "% Ating. Ponderado Ajustado" por filial/mês) — sem essa carga, a
comissão de GN de contratos de meses anteriores à janela do RPA fica sempre
`None` (nenhum FATOR_META encontrado pra calcular a faixa de comissão).

Executar com:
    python -m app.seed_producao_por_filial /caminho/arquivo.xlsx 2026-01-01 2026-08-31
"""

import sys
from datetime import datetime

from app.core.logging import configure_logging
from app.services.historical_seed import seed_from_spreadsheet

configure_logging()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Uso: python -m app.seed_producao_por_filial /caminho/arquivo.xlsx AAAA-MM-DD AAAA-MM-DD",
            file=sys.stderr,
        )
        sys.exit(1)
    xlsx_path, date_from_str, date_to_str = sys.argv[1:4]
    seed_from_spreadsheet(
        report_name="apuracao_parceiro_resumo",
        tile_key="bloco_metas_por_filial",
        metric_name="producao_por_filial",
        sheet_name="db_Metas",
        xlsx_path=xlsx_path,
        date_from=datetime.strptime(date_from_str, "%Y-%m-%d").date(),
        date_to=datetime.strptime(date_to_str, "%Y-%m-%d").date(),
    )
