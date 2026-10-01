"""
Teste manual (não faz parte da suíte formal) do módulo excel_sync.py contra
um workbook sintético que reproduz a estrutura REAL descoberta na inspeção do
Construcao.xlsx do usuário (2026-09-24) — sem depender do RPA de verdade
(baixar_looker_bruto é substituído por uma função fake).

Roda com: python -m app.services._test_excel_sync_manual
"""

import sys
from copy import copy
from datetime import date, datetime

import openpyxl
import pandas as pd
from openpyxl.styles import Font, PatternFill

sys.path.insert(0, ".")

import app.services.excel_sync as excel_sync
from app.services.excel_sync import (
    AtualizacaoRecusada,
    arrastar_base_final,
    atualizar_db_apuracaoavista,
    atualizar_db_mercado,
    atualizar_db_pagasanalitico,
    atualizar_db_pagasanalitico_ultimos_dias,
)


def montar_workbook_sintetico() -> openpyxl.Workbook:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # --- db_pagasanalitico: 12 col fórmula (A:L) + col brutas a partir de M ---
    ws = wb.create_sheet("db_pagasanalitico")
    formula_cols = ["ANO", "MES", "CHAVE_CONTRATO", "CHAVE_AREA_EHS", "AREA_LOJA_EHS", "FILIAL_CONTRATO",
                     "CHAVE_LOJA", "CNPJ_LOJA", "CODIGO_LOJA", "NOME_LOJA", "PRODUTO EGV", "SEGURO"]
    raw_cols = ["ID Proposta", "Dt Relatório", "Lojista", "Status Proposta", "Cd Contrato", "Vl Financiamento"]
    header = formula_cols + raw_cols
    ws.append(header)
    ws.append([
        "=YEAR(N2)", "=MONTH(N2)", '=AC2&"."&S2', "=1", "=2", "=3", "=4", "=5", "=6", "=7", "=8", "=9",
        1001, datetime(2026, 9, 20), "10 - X - 111", "PROPOSTA PAGA", "AU001", 1000.0,
    ])
    # Formatação real (moeda + fonte em negrito + fundo colorido) na
    # linha-modelo — pra testar se a linha nova herda o ESTILO completo, não
    # só o valor (achado real em 2026-09-24: 1ª correção só copiava
    # number_format, usuário reportou que fonte/cor ainda ficavam default).
    col_vl_financiamento = header.index("Vl Financiamento") + 1
    cel_modelo = ws.cell(row=2, column=col_vl_financiamento)
    cel_modelo.number_format = "R$ #,##0.00"
    cel_modelo.font = Font(bold=True, color="FF0000")
    cel_modelo.fill = PatternFill("solid", fgColor="FFFF00")
    # Mesma ideia numa coluna de FÓRMULA (ANO, col 1) — testa se `_arrastar_linha`
    # também copia estilo, não só `_escrever_linhas_brutas`.
    ws.cell(row=2, column=1).fill = PatternFill("solid", fgColor="00FF00")

    # --- db_apuracaoavista: só colunas brutas ---
    ws = wb.create_sheet("db_apuracaoavista")
    ws.append(["Anomes Apuracao", "Cd Contrato", "Status Contrato", "Lojista", "R$ Principal Total", "% Fator Ajuste Produção"])
    ws.append(["202608", "AU000", "Ativo", "10 - X - 111", 5000.0, 0.85])
    ws.cell(row=2, column=6).number_format = "0.0%"

    # --- db_mercado: 6 col fórmula (A:F) + brutas a partir de G ---
    ws = wb.create_sheet("db_mercado")
    formula_cols_m = ["DATA1", "DATA2", "CHAVE_LOJA", "AREA_LOJA_EHS", "COD_LOJA", "GRUPO LOJA"]
    raw_cols_m = ["Nome Gp", "CNPJ Loja", "Mês", "Produção C6"]
    ws.append(formula_cols_m + raw_cols_m)
    ws.append(["=YEAR(I2)", "=MONTH(I2)", "=1", "=2", "=3", "=4", "BRUNO", "111", datetime(2026, 8, 1), 100.0])

    # --- base_final: header em 2 linhas, dados a partir da linha 3 ---
    ws = wb.create_sheet("base_final")
    ws.append(["DATA", "CONTRATO", "VALOR_FINANC"])
    ws.append(["ANO", "COD_CONTRATO", "VALOR_FINANCIAMENTO_R$"])
    ws.append(["=YEAR(B3)", "=db_apuracaoavista!B2", "=db_apuracaoavista!E2"])

    for nome in ("db_carterizacao", "config_carteira", "config_AjustesContrato", "config_GNs"):
        wb.create_sheet(nome)

    return wb


def fake_baixar(report_name, tile_key, *, filter_query_override=None, filter_value_override=None, sessao=None, evidencias=None):
    if report_name == "acompanhamento_veiculos":
        # "Vl Financiamento" vem como TEXTO no formato do Looker (ex.: "R$
        # 2,000.00"), igual ao CSV real baixado em 2026-09-24 — reproduz o
        # bug real (linha nova ficava com string em vez de número, diferente
        # das linhas antigas, que sempre tiveram float de verdade).
        return pd.DataFrame({
            "ID Proposta": [2001, 2002],
            "Dt Relatório": [datetime(2026, 9, 24), datetime(2026, 9, 24)],
            "Lojista": ["20 - Y - 222", "20 - Y - 222"],
            "Status Proposta": ["PROPOSTA PAGA", "PROPOSTA APROVADA"],
            "Cd Contrato": ["AU100", "AU101"],
            "Vl Financiamento": ["R$ 2,000.00", "R$ 3,000.00"],
        })
    if report_name == "comissao_avista":
        # Reproduz o bug real encontrado em 2026-09-24: o CSV baixado do Looker
        # tinha uma linha de rodapé/total com "Anomes Apuracao" vazio, o que
        # promove a coluna inteira pra float64 (202609 -> 202609.0) — daí um
        # `.astype(str)` ingênuo gerava "202609.0" e nunca batia com "202609"
        # (430 linhas baixadas, 0 batendo). Aqui simulamos exatamente isso:
        # valores float com .0 de sobra, mais uma linha de rodapé com NaN.
        # "% Fator Ajuste Produção" reproduz o bug real de 2026-09-30: vem
        # como TEXTO com "." decimal (locale do Looker, não o BR "89,3%"),
        # e sem tratamento ficava assim mesmo na planilha (não virava número).
        return pd.DataFrame({
            "Anomes Apuracao": [202609.0, 202609.0, float("nan")],
            "Cd Contrato": ["AU200", "AU201", None],
            "Status Contrato": ["Ativo", "Ativo", None],
            "Lojista": ["30 - Z - 333", "30 - Z - 333", None],
            "R$ Principal Total": [7000.0, 8000.0, 15000.0],
            "% Fator Ajuste Produção": ["89.3%", "0.0%", None],
        })
    if report_name == "painel_visita_mercado":
        # Reproduz o bug real de 2026-09-25: CNPJ veio como float puro (o
        # pandas lê dígitos sem pontuação como número — sem tratamento
        # especial isso vira notação científica no Excel) e "Produção C6"
        # veio abreviado ("510.8 mil"), formato que o parser antigo não
        # reconhecia (só entendia "R$ ...").
        return pd.DataFrame({
            "Nome Gp": ["BRUNO"],
            "CNPJ Loja": [37748240000189.0],
            "Mês": [datetime(2026, 9, 1)],
            "Produção C6": ["510.8 mil"],
        })
    raise AssertionError(f"relatório inesperado no teste: {report_name}")


def main():
    excel_sync.baixar_looker_bruto = fake_baixar

    wb = montar_workbook_sintetico()

    print("== atualizar_db_pagasanalitico (dia 2026-09-24) ==")
    res = atualizar_db_pagasanalitico(wb, date(2026, 9, 24))
    print(res)
    ws = wb["db_pagasanalitico"]
    assert ws.max_row == 4, f"esperava 4 linhas (header+3 dados), veio {ws.max_row}"
    assert ws.cell(row=3, column=13).value == 2001, "ID Proposta da linha nova errado"
    formula_ano_linha3 = ws.cell(row=3, column=1).value
    assert formula_ano_linha3 == "=YEAR(N3)", f"fórmula ANO não arrastou certo: {formula_ano_linha3!r}"
    formula_chave_linha4 = ws.cell(row=4, column=3).value
    assert formula_chave_linha4 == '=AC4&"."&S4', f"fórmula CHAVE_CONTRATO não arrastou certo: {formula_chave_linha4!r}"
    # `cell.fill` devolve um StyleProxy sem __eq__ de verdade (compara sempre
    # False mesmo com conteúdo idêntico) — copy() desembrulha pro PatternFill
    # real, que aí sim compara por valor.
    assert copy(ws.cell(row=3, column=1).fill) == copy(ws.cell(row=2, column=1).fill), (
        "cor de fundo da coluna de fórmula (ANO) não foi copiada pra linha nova"
    )
    print("  OK: linhas inseridas, fórmulas arrastadas e estilo da coluna de fórmula copiado.\n")

    print("== conferindo normalização de valor monetário + estilo completo (bug real 2026-09-24) ==")
    col_vl_financiamento = 18  # "Vl Financiamento" é a 6ª coluna bruta, após 12 de fórmula (12+6=18)
    cel_modelo = ws.cell(row=2, column=col_vl_financiamento)
    cel_linha3 = ws.cell(row=3, column=col_vl_financiamento)
    valor_linha3 = cel_linha3.value
    assert isinstance(valor_linha3, float), (
        f"'Vl Financiamento' devia ter virado float (era 'R$ 2,000.00' baixado como texto), "
        f"veio {type(valor_linha3).__name__}: {valor_linha3!r}"
    )
    assert valor_linha3 == 2000.0, f"valor convertido errado: {valor_linha3!r}"
    assert cel_linha3.number_format == cel_modelo.number_format, (
        f"number_format não foi copiado: modelo={cel_modelo.number_format!r}, linha nova={cel_linha3.number_format!r}"
    )
    assert copy(cel_linha3.font) == copy(cel_modelo.font), (
        f"fonte não foi copiada: modelo={cel_modelo.font!r}, linha nova={cel_linha3.font!r}"
    )
    assert copy(cel_linha3.fill) == copy(cel_modelo.fill), (
        f"cor de fundo não foi copiada: modelo={cel_modelo.fill!r}, linha nova={cel_linha3.fill!r}"
    )
    print(
        f"  OK: 'R$ 2,000.00' virou {valor_linha3!r} (float), e number_format/fonte/fundo "
        "copiados da linha-modelo.\n"
    )

    print("== atualizar_db_apuracaoavista (mês 202609) ==")
    res = atualizar_db_apuracaoavista(wb, "202609")
    print(res)
    ws = wb["db_apuracaoavista"]
    assert ws.max_row == 4, f"esperava 4 linhas (header + 1 antiga + 2 novas), veio {ws.max_row}"
    assert ws.cell(row=2, column=2).value == "AU000", "linha antiga (202608) não deveria ter sido tocada"
    assert ws.cell(row=3, column=2).value == "AU200", "1ª linha nova errada"
    assert ws.cell(row=4, column=2).value == "AU201", "2ª linha nova errada"
    print("  OK: linha antiga preservada, linhas novas no lugar certo.\n")

    print("== conferindo normalização de valor percentual (bug real 2026-09-30) ==")
    col_fator = 6  # "% Fator Ajuste Produção"
    fator_linha3 = ws.cell(row=3, column=col_fator).value
    fator_linha4 = ws.cell(row=4, column=col_fator).value
    assert isinstance(fator_linha3, float), (
        f"'% Fator Ajuste Produção' devia ter virado float (era '89.3%' baixado como texto), "
        f"veio {type(fator_linha3).__name__}: {fator_linha3!r}"
    )
    assert abs(fator_linha3 - 0.893) < 1e-9, f"valor percentual convertido errado: {fator_linha3!r}"
    assert fator_linha4 == 0.0, f"'0.0%' deveria virar 0.0, veio {fator_linha4!r}"
    assert ws.cell(row=3, column=col_fator).number_format == "0.0%", (
        "number_format percentual não foi copiado da linha-modelo"
    )
    print(f"  OK: '89.3%' virou {fator_linha3!r} e '0.0%' virou {fator_linha4!r} (fração, não texto).\n")

    print("== arrastar_base_final ==")
    res = arrastar_base_final(wb)
    print(res)
    ws_bf = wb["base_final"]
    assert ws_bf.max_row == 5, f"esperava base_final ir até a linha 5 (2 header + 3 dados), veio {ws_bf.max_row}"
    f_contrato_l4 = ws_bf.cell(row=4, column=2).value
    f_contrato_l5 = ws_bf.cell(row=5, column=2).value
    assert f_contrato_l4 == "=db_apuracaoavista!B3", f"referência posicional errada (linha 4): {f_contrato_l4!r}"
    assert f_contrato_l5 == "=db_apuracaoavista!B4", f"referência posicional errada (linha 5): {f_contrato_l5!r}"
    print("  OK: base_final acompanhou db_apuracaoavista com o deslocamento certo (2 linhas novas).\n")

    print("== atualizar_db_mercado (mês 202609) ==")
    res = atualizar_db_mercado(wb, "202609")
    print(res)
    ws = wb["db_mercado"]
    assert ws.max_row == 3
    assert res["check_quantidade_bate"] is True
    print("  OK.\n")

    print("== conferindo CNPJ como texto + valor abreviado (bug real 2026-09-25) ==")
    col_cnpj = 8  # "CNPJ Loja": G=7 Nome Gp, H=8 CNPJ Loja
    col_producao = 10  # J=10 Produção C6
    cnpj_linha3 = ws.cell(row=3, column=col_cnpj).value
    assert isinstance(cnpj_linha3, str), (
        f"CNPJ devia ter virado texto (era float puro 37748240000189.0), "
        f"veio {type(cnpj_linha3).__name__}: {cnpj_linha3!r}"
    )
    assert cnpj_linha3 == "37748240000189", f"CNPJ convertido errado: {cnpj_linha3!r}"
    producao_linha3 = ws.cell(row=3, column=col_producao).value
    assert isinstance(producao_linha3, float), (
        f"'Produção C6' devia ter virado float (era '510.8 mil' abreviado), "
        f"veio {type(producao_linha3).__name__}: {producao_linha3!r}"
    )
    assert producao_linha3 == 510800.0, f"valor abreviado convertido errado: {producao_linha3!r}"
    print(f"  OK: CNPJ virou {cnpj_linha3!r} (texto) e '510.8 mil' virou {producao_linha3!r} (float).\n")

    print("== testando recusa (mês fora de ordem em db_apuracaoavista) ==")
    try:
        atualizar_db_apuracaoavista(wb, "202601")
        raise AssertionError("deveria ter recusado!")
    except AtualizacaoRecusada as exc:
        print("  OK, recusou como esperado:", exc)

    print("\n== testando SUBSTITUIÇÃO (rodar o mesmo dia de novo, com dado diferente) ==")

    def fake_baixar_v2(report_name, tile_key, **kwargs):
        return pd.DataFrame({
            "ID Proposta": [3001, 3002, 3003],
            "Dt Relatório": [datetime(2026, 9, 24)] * 3,
            "Lojista": ["40 - W - 444"] * 3,
            "Status Proposta": ["PROPOSTA PAGA", "PROPOSTA PAGA", "PROPOSTA REPROVADA"],
            "Cd Contrato": ["AU300", "AU301", "AU302"],
            "Vl Financiamento": [500.0, 600.0, 700.0],
        })

    excel_sync.baixar_looker_bruto = fake_baixar_v2
    linhas_antes = wb["db_pagasanalitico"].max_row
    res = atualizar_db_pagasanalitico(wb, date(2026, 9, 24))
    print(res)
    ws = wb["db_pagasanalitico"]
    linhas_depois = ws.max_row
    assert res["linhas_baixadas"] == 3
    assert linhas_depois == linhas_antes + 1, (
        f"esperava +1 linha no total (2 antigas removidas, 3 novas inseridas: -2+3=+1), "
        f"veio antes={linhas_antes} depois={linhas_depois}"
    )
    ultimo_id = ws.cell(row=linhas_depois, column=13).value
    assert ultimo_id == 3003, f"última linha deveria ser a proposta 3003 (substituição), veio {ultimo_id}"
    penultimo_id = ws.cell(row=linhas_depois - 2, column=13).value
    assert penultimo_id == 3001, f"linhas antigas do dia 24/09 não foram removidas — achei {penultimo_id} onde esperava 3001"
    print("  OK: linhas antigas do dia removidas e substituídas pelas novas, fórmulas arrastadas certo.\n")

    print("== testando atualizar_db_pagasanalitico_ultimos_dias (preenche buraco de dias esquecidos) ==")

    import re as _re

    def fake_baixar_dias(report_name, tile_key, *, filter_query_override=None, **kwargs):
        assert report_name == "acompanhamento_veiculos"
        m = _re.search(r"Dt\+Relatorio\+Date=(\d{4}-\d{2}-\d{2})", filter_query_override)
        dia_pedido = m.group(1)
        dia_num = int(dia_pedido[-2:])
        return pd.DataFrame({
            "ID Proposta": [9000 + dia_num],
            "Dt Relatório": [datetime.strptime(dia_pedido, "%Y-%m-%d")],
            "Lojista": ["50 - K - 555"],
            "Status Proposta": ["PROPOSTA PAGA"],
            "Cd Contrato": [f"AU9{dia_num:02d}"],
            "Vl Financiamento": [float(1000 + dia_num)],
        })

    excel_sync.baixar_looker_bruto = fake_baixar_dias
    resultados = atualizar_db_pagasanalitico_ultimos_dias(wb, date(2026, 9, 26), quantidade_dias=3)
    print(resultados)
    assert len(resultados) == 3, f"esperava 3 dias processados (24 substituído, 25/26 novos), veio {len(resultados)}"
    ws = wb["db_pagasanalitico"]
    assert ws.max_row == 5, f"esperava max_row=5 (header+modelo+3 dias), veio {ws.max_row}"
    ultimas_3 = [ws.cell(row=r, column=13).value for r in range(3, 6)]
    assert ultimas_3 == [9024, 9025, 9026], f"esperava IDs [9024,9025,9026] nas linhas 3-5, veio {ultimas_3}"
    print("  OK: dia 24 substituído e dias 25/26 preenchidos automaticamente, sem duplicar.\n")

    print("== rodando de novo os 'últimos 3 dias' (24 e 25 já cobertos, só 26 deveria atualizar) ==")
    qtd_linhas_antes = ws.max_row
    resultados2 = atualizar_db_pagasanalitico_ultimos_dias(wb, date(2026, 9, 26), quantidade_dias=3)
    print(resultados2)
    assert len(resultados2) == 1, (
        f"esperava só o dia 26 sendo reprocessado (24/25 já cobertos, devem ser pulados), "
        f"veio {len(resultados2)} resultado(s)"
    )
    assert resultados2[0]["periodo"] == "2026-09-26"
    ws = wb["db_pagasanalitico"]
    assert ws.max_row == qtd_linhas_antes, (
        f"não deveria ter mudado a quantidade de linhas (só substituiu o dia 26), "
        f"antes={qtd_linhas_antes} depois={ws.max_row}"
    )
    print("  OK: dias 24/25 pulados (já cobertos), só o dia 26 foi reprocessado — sem duplicar.\n")

    print("== testando dia SEM nenhuma linha PROPOSTA PAGA (bug real 2026-09-28) ==")

    def fake_baixar_sem_paga(report_name, tile_key, **kwargs):
        return pd.DataFrame({
            "ID Proposta": [7001, 7002],
            "Dt Relatório": [datetime(2026, 9, 27)] * 2,
            "Lojista": ["60 - M - 666"] * 2,
            "Status Proposta": ["EM ANÁLISE", "PROPOSTA APROVADA"],
            "Cd Contrato": ["AU700", "AU701"],
            "Vl Financiamento": ["R$ 100.00", "R$ 200.00"],
        })

    excel_sync.baixar_looker_bruto = fake_baixar_sem_paga
    res_sem_paga = atualizar_db_pagasanalitico(wb, date(2026, 9, 27))
    print(res_sem_paga)
    assert res_sem_paga["linhas_paga"] == 0, f"esperava 0 linhas PAGA, veio {res_sem_paga['linhas_paga']}"
    assert res_sem_paga["soma_vl_financiamento_paga"] == 0.0, (
        f"esperava soma 0.0 (não deveria quebrar/virar string vazia), veio {res_sem_paga['soma_vl_financiamento_paga']!r}"
    )
    print("  OK: dia sem PROPOSTA PAGA não quebra o cálculo, soma fica 0.0.\n")

    print("== testando fallback de evidência quando o dia mais recente está vazio (bug real 2026-09-29) ==")

    chamadas_evidencia = []

    def fake_capturar_evidencias_producao(page, evidencias):
        chamadas_evidencia.append(page)
        evidencias.append("fake_evidencia.png")

    excel_sync._capturar_evidencias_producao = fake_capturar_evidencias_producao

    def fake_baixar_vazio_no_ultimo_dia(report_name, tile_key, *, filter_query_override=None, **kwargs):
        m = _re.search(r"Dt\+Relatorio\+Date=(\d{4}-\d{2}-\d{2})", filter_query_override)
        dia_pedido = m.group(1)
        if dia_pedido == "2026-10-01":  # dia mais recente, sem NENHUMA proposta digitada ainda
            return pd.DataFrame({
                "ID Proposta": [], "Dt Relatório": [], "Lojista": [],
                "Status Proposta": [], "Cd Contrato": [], "Vl Financiamento": [],
            })
        dia_num = int(dia_pedido[-2:])
        return pd.DataFrame({
            "ID Proposta": [8000 + dia_num],
            "Dt Relatório": [datetime.strptime(dia_pedido, "%Y-%m-%d")],
            "Lojista": ["70 - Z - 777"],
            "Status Proposta": ["PROPOSTA PAGA"],
            "Cd Contrato": [f"AU8{dia_num:02d}"],
            "Vl Financiamento": [float(2000 + dia_num)],
        })

    excel_sync.baixar_looker_bruto = fake_baixar_vazio_no_ultimo_dia
    sessao_fake = (None, object())  # placeholder — _capturar_evidencias_producao está mockada
    evidencias_teste = []
    resultados3 = atualizar_db_pagasanalitico_ultimos_dias(
        wb, date(2026, 10, 1), quantidade_dias=3, sessao=sessao_fake, evidencias=evidencias_teste
    )
    print(resultados3)
    assert len(evidencias_teste) == 1, f"esperava 1 print capturado (fallback pro dia com dado), veio {len(evidencias_teste)}"
    assert len(chamadas_evidencia) == 1, f"esperava só 1 chamada de captura de evidência, veio {len(chamadas_evidencia)}"
    print("  OK: dia mais recente (sem dado) pulado pra evidência; usou o dia anterior com dado.\n")

    print("== testando print de evidência do 'Bloco de Metas' em atualizar_db_apuracaoavista ==")

    chamadas_evidencia_apuracao = []

    def fake_capturar_evidencia_apuracao_parceiro(sessao, evidencias):
        chamadas_evidencia_apuracao.append(sessao)
        evidencias.append("fake_bloco_metas.png")

    excel_sync._capturar_evidencia_apuracao_parceiro = fake_capturar_evidencia_apuracao_parceiro

    def fake_baixar_comissao_avista(report_name, tile_key, **kwargs):
        assert report_name == "comissao_avista"
        return pd.DataFrame({
            "Anomes Apuracao": ["202609", "202609"],
            "Cd Contrato": ["AU900", "AU901"],
        })

    excel_sync.baixar_looker_bruto = fake_baixar_comissao_avista
    sessao_fake_apuracao = (None, object())  # placeholder — função de evidência está mockada
    evidencias_apuracao = []
    res_apuracao = atualizar_db_apuracaoavista(
        wb, "202609", sessao=sessao_fake_apuracao, evidencias=evidencias_apuracao
    )
    print(res_apuracao)
    assert len(chamadas_evidencia_apuracao) == 1, (
        f"esperava 1 chamada de captura de evidência (sessão já aberta reaproveitada), "
        f"veio {len(chamadas_evidencia_apuracao)}"
    )
    assert evidencias_apuracao == ["fake_bloco_metas.png"], evidencias_apuracao
    print("  OK: com sessão já aberta, print do 'Bloco de Metas' é capturado na mesma sessão.\n")

    print("== mesmo teste, sem sessão pré-aberta (evidencias pede pra abrir uma sozinha) ==")

    chamadas_evidencia_apuracao.clear()

    class _SessaoLookerFakeCtx:
        def __enter__(self):
            return (None, object())

        def __exit__(self, *args):
            return False

    excel_sync.sessao_looker = lambda: _SessaoLookerFakeCtx()
    evidencias_apuracao2 = []
    atualizar_db_apuracaoavista(wb, "202609", evidencias=evidencias_apuracao2)
    assert len(chamadas_evidencia_apuracao) == 1, (
        f"esperava 1 chamada de captura de evidência (sessão aberta sob demanda), "
        f"veio {len(chamadas_evidencia_apuracao)}"
    )
    assert evidencias_apuracao2 == ["fake_bloco_metas.png"], evidencias_apuracao2
    print("  OK: sem sessão pré-aberta, abre uma só pra esse fim e captura o print igual.\n")

    print("== conferindo filter_value_override (janela alargada pro mês anterior, bug real 2026-10-01) ==")

    janelas_recebidas = []

    def fake_baixar_com_janela(report_name, tile_key, *, filter_value_override=None, **kwargs):
        assert report_name == "comissao_avista"
        janelas_recebidas.append(filter_value_override)
        return pd.DataFrame({
            "Anomes Apuracao": ["202609"],
            "Cd Contrato": ["AU950"],
        })

    excel_sync.baixar_looker_bruto = fake_baixar_com_janela
    atualizar_db_apuracaoavista(wb, "202609", filter_value_override="3 months")
    assert janelas_recebidas == ["3 months"], (
        f"esperava filter_value_override='3 months' repassado pro baixar_looker_bruto, veio {janelas_recebidas}"
    )
    janelas_recebidas.clear()
    atualizar_db_apuracaoavista(wb, "202609")
    assert janelas_recebidas == [None], (
        f"sem override explícito, esperava None (usa o padrão '2 months' do portal_selectors.json), "
        f"veio {janelas_recebidas}"
    )
    print("  OK: filter_value_override chega até baixar_looker_bruto; sem passar, fica None (padrão).\n")

    print("\nTODOS OS TESTES PASSARAM.")


if __name__ == "__main__":
    main()
