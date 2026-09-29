"""
Diagnóstico READ-ONLY pra investigar o descompasso entre `base_final` e
`db_apuracaoavista` (ver `AtualizacaoRecusada` levantada por
`arrastar_base_final` em `excel_sync.py`). Não altera nada no arquivo, só
imprime o estado atual das duas abas pra entender de onde vêm as linhas
"extras" de base_final antes de decidir como corrigir.

Uso:
    python -m app.diagnostico_base_final --planilha "C:\\caminho\\Construcao.xlsx"
"""

import argparse
from pathlib import Path

import openpyxl

from app.services.excel_sync import _header_map, _ultima_linha_com_dado


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planilha", required=True)
    args = parser.parse_args()

    wb = openpyxl.load_workbook(Path(args.planilha), data_only=False)

    ws_av = wb["db_apuracaoavista"]
    mapa_av = _header_map(ws_av, 1)
    col_cc_av = mapa_av["Cd Contrato"]
    ultima_av = _ultima_linha_com_dado(ws_av, col_cc_av, header_row=1)
    print(f"db_apuracaoavista: última linha com dado (col 'Cd Contrato') = {ultima_av}")

    ws_bf = wb["base_final"]
    mapa_bf = _header_map(ws_bf, 2)  # cabeçalho de verdade fica na linha 2
    col_cc_bf = mapa_bf["COD_CONTRATO"]
    ultima_bf = _ultima_linha_com_dado(ws_bf, col_cc_bf, header_row=2)
    print(f"base_final: última linha com dado (col 'COD_CONTRATO') = {ultima_bf}")

    alvo_bf = ultima_av + 1  # deslocamento de +1 confirmado na inspeção real (ver arrastar_base_final)
    print(f"alvo esperado pra base_final (última linha de db_apuracaoavista + 1) = {alvo_bf}")

    if alvo_bf < ultima_bf:
        print(
            f"\n>>> base_final tem {ultima_bf - alvo_bf} linha(s) 'extra' além do esperado. "
            "Conteúdo dessas linhas:\n"
        )
        colunas_interesse = [
            c for c in ("COD_CONTRATO", "Lojista", "Status Proposta", "Anomes Apuracao", "MES", "ANO")
            if c in mapa_bf
        ]
        for r in range(alvo_bf, ultima_bf + 1):
            partes = [f"{c}={ws_bf.cell(row=r, column=mapa_bf[c]).value!r}" for c in colunas_interesse]
            print(f"  linha {r}: " + ", ".join(partes))
    else:
        print("\nSem descompasso (alvo_bf >= ultima_bf) — se o erro ainda aparecer, me manda esse print de novo.")


if __name__ == "__main__":
    main()
