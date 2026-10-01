"""
CLI pra sincronizar o Construcao.xlsx do usuário direto com o Looker — ver
`app/services/excel_sync.py` pra lógica e as regras de segurança (só mexe no
bloco final de cada aba, nunca no meio).

Uso:
    python -m app.atualizar_excel --planilha "C:\\caminho\\Construcao.xlsx" --aba db_pagasanalitico --dia 2026-09-24
    python -m app.atualizar_excel --planilha "C:\\caminho\\Construcao.xlsx" --aba db_apuracaoavista --mes 2026-09
    python -m app.atualizar_excel --planilha "C:\\caminho\\Construcao.xlsx" --aba db_mercado --mes 2026-09
    python -m app.atualizar_excel --planilha "C:\\caminho\\Construcao.xlsx" --tudo

`--tudo` roda as 3 abas no período mais recente de cada uma — db_pagasanalitico
processa hoje + os 2 dias anteriores (não só hoje: se algum dia ficou sem
rodar, o buraco é preenchido sozinho, sem duplicar o que já existe — ver
`atualizar_db_pagasanalitico_ultimos_dias` em `excel_sync.py`), mês corrente
pra db_apuracaoavista/db_mercado —, nessa ordem, e arrasta o base_final no
final — faz 1 login só no portal, reaproveitado por todos os downloads (ver
`sessao_looker` em `excel_sync.py`), em vez de logar de novo a cada aba.

Até o dia 05 de cada mês, `--tudo` TAMBÉM reprocessa o MÊS ANTERIOR em
db_apuracaoavista/db_mercado (antes do mês corrente) — achado real em
2026-10-01: essas duas apurações saem do Looker com alguns dias de atraso
em relação à virada do mês, e como a aba só aceita mexer no ÚLTIMO bloco,
pular direto pro mês corrente no dia 1º travaria o mês anterior pra sempre
(nunca mais daria pra corrigir os números finais dele). Reprocessar os
primeiros dias também serve como "check" de fechamento: o relatório final
mostra a contagem de db_apuracaoavista x PROPOSTA PAGA de db_pagasanalitico
pro mês anterior de novo, não só pro mês corrente.

Sempre que `db_apuracaoavista` for atualizada (isoladamente ou via `--tudo`),
o script arrasta o `base_final` automaticamente em seguida — é a única aba
que depende disso (ver docstring de `excel_sync.py`).

Ao salvar, marca a planilha pra recalcular tudo sozinha na próxima vez que
for aberta no Excel (`fullCalcOnLoad`) — não precisa apertar F9.

A primeira execução pode pedir confirmação manual do portal (verificação de
dispositivo) se HEADLESS não estiver "false" — rode a primeira vez com:
    $env:HEADLESS="false"; python -m app.atualizar_excel ...
pra ver o navegador e resolver isso, igual já é feito no RPA do app web.
"""

import argparse
import logging
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import openpyxl

from app.core.logging import configure_logging
from app.services.acomp_diario_evidencia import capturar_prints_acomp_diario
from app.services.excel_sync import (
    _EVIDENCIAS_DIR,
    AtualizacaoRecusada,
    arrastar_base_final,
    atualizar_db_apuracaoavista,
    atualizar_db_mercado,
    atualizar_db_pagasanalitico,
    atualizar_db_pagasanalitico_ultimos_dias,
    sessao_looker,
)
from app.services.relatorio_checks import gerar_relatorio

configure_logging()
logger = logging.getLogger(__name__)


def _backup(caminho: Path) -> Path:
    destino = caminho.with_name(f"{caminho.stem}_backup_{datetime.now():%Y%m%d_%H%M%S}{caminho.suffix}")
    shutil.copy2(caminho, destino)
    logger.info("Backup criado antes de mexer no arquivo: %s", destino)
    return destino


def _salvar_relatorio(caminho_planilha: Path, texto: str) -> Path:
    destino = caminho_planilha.with_name(
        f"{caminho_planilha.stem}_relatorio_{datetime.now():%Y%m%d_%H%M%S}.txt"
    )
    destino.write_text(texto, encoding="utf-8")
    return destino


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
    evidencias: list[Path] = []
    precisa_arrastar_base_final = False

    try:
        if args.tudo:
            hoje = date.today()
            anomes_atual = f"{hoje.year}{hoje.month:02d}"
            primeiro_dia_mes_atual = hoje.replace(day=1)
            anomes_anterior = (primeiro_dia_mes_atual - timedelta(days=1)).strftime("%Y%m")
            # Até o dia 05: mês anterior ainda pode estar "fechando" no
            # Looker — ver docstring do módulo (achado real em 2026-10-01).
            fechar_mes_anterior = hoje.day <= 5

            # 1 login só, reaproveitado pros 3 downloads (ver sessao_looker em
            # excel_sync.py) — antes disso, --tudo fazia 3 logins inteiros.
            with sessao_looker() as sessao:
                # Hoje + os 2 dias anteriores (não só hoje) — se algum dia
                # ficou sem rodar, esse buraco é preenchido sozinho aqui,
                # sem duplicar o que já existe (ver docstring da função).
                resultados.extend(
                    atualizar_db_pagasanalitico_ultimos_dias(wb, hoje, sessao=sessao, evidencias=evidencias)
                )

                if fechar_mes_anterior:
                    # SEMPRE antes do mês corrente — as duas abas só aceitam
                    # mexer no ÚLTIMO bloco, então processar o corrente
                    # primeiro travaria o anterior. Sem evidência aqui: o
                    # print do 'Bloco de Metas' já sai 1x mais abaixo, não
                    # precisa duplicar.
                    try:
                        # filter_value_override="3 months": a janela padrão
                        # ("2 months") é relativa a HOJE, não ao mês pedido —
                        # cobre bem o mês CORRENTE, mas aqui pedimos o mês
                        # anterior, que já consumiu 1 mês dessa folga (achado
                        # real em 2026-10-01: sem isso, contratos de Safra
                        # Mês mais antiga somem silenciosamente — ver
                        # docstring de atualizar_db_apuracaoavista).
                        resultados.append(
                            atualizar_db_apuracaoavista(
                                wb, anomes_anterior, sessao=sessao, filter_value_override="3 months"
                            )
                        )
                        precisa_arrastar_base_final = True
                    except AtualizacaoRecusada as exc:
                        logger.info(
                            "db_apuracaoavista: mês anterior (%s) não reprocessado — %s",
                            anomes_anterior,
                            exc,
                        )
                    try:
                        resultados.append(atualizar_db_mercado(wb, anomes_anterior, sessao=sessao))
                    except AtualizacaoRecusada as exc:
                        logger.info(
                            "db_mercado: mês anterior (%s) não reprocessado — %s",
                            anomes_anterior,
                            exc,
                        )

                resultados.append(
                    atualizar_db_apuracaoavista(wb, anomes_atual, sessao=sessao, evidencias=evidencias)
                )
                precisa_arrastar_base_final = True
                resultados.append(atualizar_db_mercado(wb, anomes_atual, sessao=sessao))
        elif args.aba == "db_pagasanalitico":
            resultados.append(atualizar_db_pagasanalitico(wb, args.dia, evidencias=evidencias))
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

    # openpyxl só escreve o TEXTO da fórmula, não recalcula nada — sem isso o
    # Excel abre mostrando o último valor calculado antes da nossa alteração
    # (errado) até o usuário apertar F9 manualmente. fullCalcOnLoad pede pro
    # Excel recalcular tudo automaticamente assim que o arquivo for aberto,
    # mesmo que o workbook esteja em modo de cálculo manual.
    wb.calculation.fullCalcOnLoad = True

    wb.save(caminho)
    logger.info("Planilha salva: %s", caminho)

    # Print dos 3 "dashboards" da aba ACOMP_DIARIO — precisa ser DEPOIS do
    # save (abre o arquivo já salvo no Excel de verdade via COM, pra
    # recalcular e printar com os números atualizados). Pedido explícito do
    # usuário em 2026-09-25; falha aqui não derruba a atualização de dado,
    # que já terminou.
    try:
        evidencias.extend(capturar_prints_acomp_diario(caminho, _EVIDENCIAS_DIR))
    except Exception as exc:
        logger.warning(
            "Não consegui tirar os prints da aba ACOMP_DIARIO (não afeta a atualização — "
            "os dados já foram salvos normalmente): %s",
            exc,
        )

    relatorio = gerar_relatorio(resultados, evidencias)
    print(relatorio)
    caminho_relatorio = _salvar_relatorio(caminho, relatorio)
    logger.info("Relatório salvo em: %s", caminho_relatorio)


if __name__ == "__main__":
    main()
