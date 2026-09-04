"""
Carga histórica única de `digitacao_analitico` a partir da planilha do
usuário (aba `db_pagasanalitico` de Construcao.xlsx) — usada porque o export
do Looker desse relatório específico tem um limite de ~500 linhas por
download (confirmado pelo usuário, 2026-09-04), inviabilizando puxar meses
de histórico via RPA (ver skill `rpa-conventions`, item 26). A partir do
primeiro dia não coberto por essa carga, o RPA (janela curta, "3 day")
assume sozinho — sem sobreposição de responsabilidade, cada um cobre um
pedaço da linha do tempo.

Aponta direto para o `Construcao.xlsx` original (várias abas) — usa
sheet_name="db_pagasanalitico", não precisa extrair a aba antes.

Lógica de parsing/substituição compartilhada em `app.services.historical_seed`
(mesmo padrão usado por `seed_comissao_avista.py` e
`seed_producao_por_filial.py` — os outros dois insumos históricos que
`base_final` também precisa).

Executar com:
    python -m app.seed_digitacao_analitico /caminho/arquivo.xlsx 2026-01-01 2026-08-31
"""

import sys
from datetime import datetime

from app.core.logging import configure_logging
from app.services.historical_seed import seed_from_spreadsheet

configure_logging()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Uso: python -m app.seed_digitacao_analitico /caminho/arquivo.xlsx AAAA-MM-DD AAAA-MM-DD",
            file=sys.stderr,
        )
        sys.exit(1)
    xlsx_path, date_from_str, date_to_str = sys.argv[1:4]
    seed_from_spreadsheet(
        report_name="acompanhamento_veiculos",
        tile_key="analitico",
        metric_name="digitacao_analitico",
        sheet_name="db_pagasanalitico",
        xlsx_path=xlsx_path,
        date_from=datetime.strptime(date_from_str, "%Y-%m-%d").date(),
        date_to=datetime.strptime(date_to_str, "%Y-%m-%d").date(),
    )
