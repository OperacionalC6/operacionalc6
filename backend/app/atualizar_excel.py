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
rodar, o buraco é preenchido sozinho, sem duplicar o que já existe), mês
corrente pra db_apuracaoavista/db_mercado —, nessa ordem, e arrasta o
base_final no final.

Até o dia 05 de cada mês, `--tudo` TAMBÉM reprocessa o MÊS ANTERIOR em
db_apuracaoavista/db_mercado (antes do mês corrente) — achado real em
2026-10-01: essas duas apurações saem do Looker com alguns dias de atraso
em relação à virada do mês, e como a aba só aceita mexer no ÚLTIMO bloco,
pular direto pro mês corrente no dia 1º travaria o mês anterior pra sempre
(nunca mais daria pra corrigir os números finais dele). Reprocessar os
primeiros dias também serve como "check" de fechamento: o relatório final
mostra a contagem de db_apuracaoavista x PROPOSTA PAGA de db_pagasanalitico
pro mês anterior de novo, não só pro mês corrente.

DOIS ACESSOS LOOKER (desde 2026-10-13): a partir de out/26 a informação do
negócio foi dividida em 2 logins diferentes no Looker (parceiros "002921" e
"003881" — ver `ContaLooker`/`contas_looker()` em
`app/services/connectors/portal_rpa.py`), cada um só enxergando a fatia
dele. TODA atualização (inclusive `--aba` isolada) agora loga nas 2 contas e
EMPILHA (concat) o resultado antes de escrever na planilha — `--tudo` faz
isso de forma eficiente (`baixar_tudo_multi_conta` em `excel_sync.py`: 1
sessão por conta cobre TODOS os downloads daquela execução); `--aba` usa
`baixar_de_todas_contas`, mais simples (1 sessão por conta só pra aquele
download). Os prints de evidência saem 1x PRA CADA conta (nome do arquivo
identifica qual é qual). Credenciais de cada conta vêm do .env
(C6_PORTAL_USERNAME_002921/_PASSWORD_002921 e
C6_PORTAL_USERNAME_003881/_PASSWORD_003881) — cada uma com seu próprio
perfil de navegador salvo (aprovação de dispositivo na 1ª vez é por conta,
não só 1x no total).

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
    _baixar_apuracaoavista,
    _baixar_mercado,
    _baixar_pagasanalitico_dia,
    arrastar_base_final,
    baixar_de_todas_contas,
    baixar_tudo_multi_conta,
    escrever_apuracaoavista,
    escrever_mercado,
    escrever_pagasanalitico_dia,
    escrever_pagasanalitico_ultimos_dias,
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

            # Baixa TUDO das 2 contas Looker configuradas (1 sessão por
            # conta, cobrindo todos os downloads desta execução) e empilha
            # (concat) cada relatório/período — ver docstring do módulo e de
            # `baixar_tudo_multi_conta` em excel_sync.py. NÃO mexe na
            # planilha ainda.
            dado = baixar_tudo_multi_conta(
                hoje,
                anomes_atual=anomes_atual,
                anomes_anterior=anomes_anterior if fechar_mes_anterior else None,
            )
            evidencias.extend(dado["evidencias"])

            # Escrita: só agora, com o dado já empilhado das 2 contas — mesma
            # ordem/regras de segurança de sempre (mês anterior SEMPRE antes
            # do corrente, porque as duas abas só aceitam mexer no ÚLTIMO
            # bloco; processar o corrente primeiro travaria o anterior).
            resultados.extend(escrever_pagasanalitico_ultimos_dias(wb, dado["pagasanalitico"]))

            if fechar_mes_anterior:
                try:
                    resultados.append(
                        escrever_apuracaoavista(wb, anomes_anterior, dado["apuracaoavista_anterior"])
                    )
                    precisa_arrastar_base_final = True
                except AtualizacaoRecusada as exc:
                    logger.info(
                        "db_apuracaoavista: mês anterior (%s) não reprocessado — %s",
                        anomes_anterior,
                        exc,
                    )
                try:
                    resultados.append(escrever_mercado(wb, anomes_anterior, dado["mercado_anterior"]))
                except AtualizacaoRecusada as exc:
                    logger.info(
                        "db_mercado: mês anterior (%s) não reprocessado — %s",
                        anomes_anterior,
                        exc,
                    )

            resultados.append(escrever_apuracaoavista(wb, anomes_atual, dado["apuracaoavista_atual"]))
            precisa_arrastar_base_final = True
            resultados.append(escrever_mercado(wb, anomes_atual, dado["mercado_atual"]))
        elif args.aba == "db_pagasanalitico":
            df = baixar_de_todas_contas(
                lambda sessao: _baixar_pagasanalitico_dia(args.dia, sessao=sessao, evidencias=evidencias)
            )
            resultados.append(escrever_pagasanalitico_dia(wb, args.dia, df))
        elif args.aba == "db_apuracaoavista":
            anomes = args.mes.replace("-", "")
            df = baixar_de_todas_contas(lambda sessao: _baixar_apuracaoavista(anomes, sessao=sessao))
            resultados.append(escrever_apuracaoavista(wb, anomes, df))
            precisa_arrastar_base_final = True
        elif args.aba == "db_mercado":
            anomes = args.mes.replace("-", "")
            df = baixar_de_todas_contas(lambda sessao: _baixar_mercado(anomes, sessao=sessao))
            resultados.append(escrever_mercado(wb, anomes, df))

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
