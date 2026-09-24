"""
CLI pra sincronizar o Construcao.xlsx do usuário direto com o Looker — ver
`app/services/excel_sync.py` pra lógica e as regras de segurança (só mexe no
bloco final de cada aba, nunca no meio).

Uso:
    python -m app.atualizar_excel --planilha "C:\\caminho\\Construcao.xlsx" --aba db_pagasanalitico --dia 2026-09-24
    python -m app.atualizar_excel --planilha "C:\\caminho\\Construcao.xlsx" --aba db_apuracaoavista --mes 2026-09
    python -m app.atualizar_excel --planilha "C:\\caminho\\Construcao.xlsx" --aba db_mercado --mes 2026-09
    python -m app.atualizar_excel --planilha "C:\\caminho\\Construcao.xlsx" --tudo

`--tudo` roda as 3 abas no período mais recente de cada uma (dia de hoje pra
db_pagasanalitico, mês corrente pra db_apuracaoavista/db_mercado), nessa
ordem, e arrasta o base_final no final.

Sempre que `db_apuracaoavista` for atualizada (isoladamente ou via `--tudo`),
o script arrasta o `base_final` automaticamente em seguida — é a única aba
que depende disso (ver docstring de `excel_sync.py`).

A primeira execução pode pedir confirmação manual do portal (verificação de
dispositivo) se HEADLESS não estiver "false" — rode a primeira vez com:
    $env:HEADLESS="false"; python -m app.atualizar_excel ...
pra ver o navegador e resolver isso, igual já é feito no RPA do app web.
"""

import argparse
import logging
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

from app.core.logging import configure_logging
from app.services.excel_sync import (
    AtualizacaoRecusada,
    arrastar_base_final,
    atualizar_db_apuracaoavista,
    atualizar_db_mercado,
    atualizar_db_pagasanalitico,
)

configure_logging()
logger = logging.getLogger(__name__)


def _backup(caminho: Path) -> Path:
    destino = caminho.with_name(f"{caminho.stem}_backup_{datetime.now():%Y%m%d_%H%M%S}{caminho.suffix}")
    shutil.copy2(caminho, destino)
    logger.info("Backup criado antes de mexer no arquivo: %s", destino)
    return destino


def _imprimir_resultado(res: dict) -> None:
    print(f"\n--- {res['aba']} ({res.get('periodo', '')}) ---")
    for chave, valor in res.items():
        if chave in ("aba", "periodo"):
            continue
        print(f"  {chave}: {valor}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--planilha", required=True, help="Caminho completo do Construcao.xlsx.")
    parser.add_argument(
        "--aba",
        choices=["db_pagasanalitico", "db_apuracaoavista", "db_mercado"],
        help="Qual aba atualizar (omitir junto com --tudo pra rodar as 3).",
    )
    parser.add_argument("--dia", type=date.fromisoformat, help="AAAA-MM-DD — só pra db_pagasanalitico.")
    parser.add_argument("--mes", help="AAAA-MM — pra db_apuracaoavista/db_mercado.")
    parser.add_argument("--tudo", action="store_true", help="Atualiza as 3 abas no período mais recente de cada uma.")
    parser.add_argument(
        "--sem-backup",
        action="store_true",
        help="Não faz cópia de segurança do arquivo antes de alterar (não recomendado).",
    )
    args = parser.parse_args()

    if not args.tudo and not args.aba:
        parser.error("Passe --aba <nome> ou --tudo.")
    if args.aba == "db_pagasanalitico" and not args.dia:
        parser.error("--aba db_pagasanalitico precisa de --dia AAAA-MM-DD.")
    if args.aba in ("db_apuracaoavista", "db_mercado") and not args.mes:
        parser.error(f"--aba {args.aba} precisa de --mes AAAA-MM.")

    caminho = Path(args.planilha)
    if not caminho.exists():
        parser.error(f"Arquivo não encontrado: {caminho}")

    if not args.sem_backup:
        _backup(caminho)

    wb = openpyxl.load_workbook(caminho, data_only=False)
    resultados: list[dict] = []
    precisa_arrastar_base_final = False

    try:
        if args.tudo:
            hoje = date.today()
            anomes_atual = f"{hoje.year}{hoje.month:02d}"
            resultados.append(atualizar_db_pagasanalitico(wb, hoje))
            resultados.append(atualizar_db_apuracaoavista(wb, anomes_atual))
            precisa_arrastar_base_final = True
            resultados.append(atualizar_db_mercado(wb, anomes_atual))
        elif args.aba == "db_pagasanalitico":
            resultados.append(atualizar_db_pagasanalitico(wb, args.dia))
        elif args.aba == "db_apuracaoavista":
            anomes = args.mes.replace("-", "")
            resultados.append(atualizar_db_apuracaoavista(wb, anomes))
            precisa_arrastar_base_final = True
        elif args.aba == "db_mercado":
            anomes = args.mes.replace("-", "")
            resultados.append(atualizar_db_mercado(wb, anomes))

        if precisa_arrastar_base_final:
            resultados.append(arrastar_base_final(wb))

    except AtualizacaoRecusada as exc:
        logger.error("Atualização recusada — nada foi alterado no arquivo: %s", exc)
        sys.exit(1)
    except Exception:
        logger.exception("Erro inesperado — o arquivo NÃO foi salvo (o backup, se feito, está intacto).")
        sys.exit(1)

    wb.save(caminho)
    logger.info("Planilha salva: %s", caminho)

    for res in resultados:
        _imprimir_resultado(res)


if __name__ == "__main__":
    main()
