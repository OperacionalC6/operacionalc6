"""
Carga histórica única de `comissao_avista` a partir da planilha do usuário
(aba `db_apuracaoavista` de Construcao.xlsx) — mesma razão e mesmo padrão de
`seed_digitacao_analitico.py` (ver docstring lá, e skill `rpa-conventions`
item 26): export do Looker limitado a ~500 linhas por download inviabiliza
puxar meses de histórico via RPA.

`comissao_avista` é a base-fato principal de `base_final` (uma linha por
contrato) — sem essa carga, `base_final` retorna 0 contratos pra qualquer mês
anterior à janela que o RPA já cobriu (achado em produção 2026-09-04: Jan/26
retornava "0 de 0 contratos" mesmo depois da carga de `digitacao_analitico`).

Executar com:
    python -m app.seed_comissao_avista /caminho/arquivo.xlsx 2026-01-01 2026-08-31
"""

import sys
from datetime import datetime

from app.core.logging import configure_logging
from app.services.historical_seed import seed_from_spreadsheet

configure_logging()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "Uso: python -m app.seed_comissao_avista /caminho/arquivo.xlsx AAAA-MM-DD AAAA-MM-DD",
            file=sys.stderr,
        )
        sys.exit(1)
    xlsx_path, date_from_str, date_to_str = sys.argv[1:4]
    seed_from_spreadsheet(
        report_name="comissao_avista",
        tile_key="analitico",
        metric_name="comissao_avista",
        sheet_name="db_apuracaoavista",
        xlsx_path=xlsx_path,
        date_from=datetime.strptime(date_from_str, "%Y-%m-%d").date(),
        date_to=datetime.strptime(date_to_str, "%Y-%m-%d").date(),
    )
