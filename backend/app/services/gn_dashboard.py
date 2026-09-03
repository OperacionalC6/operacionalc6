"""
Fase 2 do dashboard de comissão de GN (ver skill `project-context`): recalcula,
por área/GN e período, os indicadores de negócio que a aba `DashAreaGN` da
planilha do usuário mostra — sem depender do Excel, direto dos dados já
ingeridos (`metrics`, via RPA) cruzados com o cadastro (Fase 1).

Escopo combinado com o usuário (2026-09-03): só os NÚMEROS DE NEGÓCIO
(contratos, produção, mercado, share) — não os rankings/ordenações auxiliares
da planilha (isso é só apresentação, a tela web ordena por qualquer coluna).

Duas simplificações deliberadas em relação à planilha original, ambas
combinadas com o usuário ou justificadas por uma inconsistência real
encontrada na própria fórmula (não são "atalho" por preguiça — documentadas
aqui pra não serem desfeitas sem motivo):

1. **Área da loja** = `StoreRegistryMonthly.carterizacao_ehs` diretamente.
   A coluna `AREA_LOJA_EHS` do `base_final` original tem uma inconsistência
   real (a fórmula usa Filial como valor primário e só cai pra
   CARTERIZACAO_EHS num fallback que quase nunca dispara — provavelmente um
   copy-paste não ajustado da fórmula vizinha `AREA_LOJA_C6`). Usar
   CARTERIZACAO_EHS direto é o que a própria planilha faz pra MONTAR a lista
   de lojas por área na `DashAreaGN` (colunas auxiliares AS:BJ), então é a
   fonte de verdade real, não a coluna `AREA_LOJA_EHS` em si.

2. **Metas** (META QTD CONTRATO, META SHARE, PRODUÇÃO META POTENCIAL) foram
   deixadas de fora desta primeira versão — as fórmulas originais dependem de
   uma cadeia que não ficou clara na leitura das fórmulas (ex.: META SHARE
   referencia SHARE MÉDIA ULT3M de um jeito que parece incompleto) e "mercado
   médio últimos 3 meses" na planilha usa um filtro de ano/mês HARDCODED
   (2026, mês>=6) que ficaria errado assim que o tempo passasse — não faz
   sentido replicar isso literalmente. Implementamos aqui a versão com
   sentido real (média móvel dos últimos 3 meses fechados antes do período
   pedido). Metas ficam para uma iteração futura, sob demanda.

Os campos `mercado_*_referencia`/`share_mes_referencia` NÃO são necessariamente do
mês pedido em `mes` — o relatório de mercado (`painel_visita_mercado`) só consegue
trazer o mês FECHADO mais recente (`{last_closed_month}` no RPA, ver
rpa-conventions item 22), nunca o mês corrente. Usamos o mês mais recente
disponível pra loja, devolvido em `mercado_mes_referencia`, em vez de exigir
correspondência exata com `mes` — do contrário esses campos ficariam sempre
`None` sempre que alguém pedisse o mês corrente (o caso mais comum de uso).
`producao_mes`/`qtd_contratos_mes` (comissão/financiamento) não têm esse
problema — vêm de relatórios com janela relativa, sempre atualizados.
"""

import re
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.metric import Metric
from app.models.store_commercial_terms import StoreCommercialTerms
from app.models.store_registry_monthly import StoreRegistryMonthly
from app.services.connectors.base import parse_looker_number

# Formato real confirmado em export do Looker: "68322 - 07452301000103 - NOME DA LOJA"
# (Cd Loja - CNPJ 14 dígitos - Nome) — mais robusto que a fórmula original da planilha
# (RIGHT(LEFT(...,22),14), que assume posição fixa) porque não depende do Cd Loja ter
# sempre a mesma quantidade de dígitos.
_LOJISTA_CNPJ_RE = re.compile(r"^\s*\d+\s*-\s*(\d{14})\s*-")


def _extract_cnpj(lojista: object) -> str | None:
    if not isinstance(lojista, str):
        return None
    match = _LOJISTA_CNPJ_RE.match(lojista)
    return match.group(1) if match else None


def _norm_cnpj(value: object) -> str | None:
    """
    Normaliza um CNPJ vindo de `dimensions` (JSONB) pra string de dígitos.
    Descoberto em teste real (2026-09-03): a coluna "CNPJ Loja" do export do
    Looker é NUMÉRICA (int64 no pandas) — vira número no JSON, não string —
    então comparar direto contra as chaves de `store_registry_monthly.cnpj_loja`
    (sempre string) nunca batia e todo cruzamento de mercado ficava `None`
    silenciosamente. "Lojista" (a outra fonte de CNPJ, via regex) já vem como
    string, então essa função é um no-op nesse caso — mantida em todo lugar
    que lê CNPJ de `dimensions` por segurança.
    """
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def _to_float(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def list_areas(db: Session, ano: int, mes: int) -> list[str]:
    """Áreas com cadastro de loja no período — alimenta o seletor da tela."""
    rows = (
        db.query(StoreRegistryMonthly.carterizacao_ehs)
        .filter(
            StoreRegistryMonthly.ano == ano,
            StoreRegistryMonthly.mes == mes,
            StoreRegistryMonthly.carterizacao_ehs.isnot(None),
        )
        .distinct()
        .order_by(StoreRegistryMonthly.carterizacao_ehs)
        .all()
    )
    return [r[0] for r in rows]


def get_area_scorecard(db: Session, area: str, ano: int, mes: int) -> dict:
    """
    Indicadores de negócio por loja da área pedida, no mês pedido — equivalente
    da tabela de lojas da `DashAreaGN` (sem as colunas de meta, ver docstring
    do módulo).
    """
    periodo = date(ano, mes, 1)

    lojas = (
        db.query(StoreRegistryMonthly)
        .filter(
            StoreRegistryMonthly.carterizacao_ehs == area,
            StoreRegistryMonthly.ano == ano,
            StoreRegistryMonthly.mes == mes,
        )
        .all()
    )
    lojas_por_cnpj = {l.cnpj_loja: l for l in lojas if l.cnpj_loja}
    if not lojas_por_cnpj:
        return {"area": area, "ano": ano, "mes": mes, "lojas": []}

    # Nome comercial da loja (mais confiável que o cadastro de carterização, que
    # às vezes tem o nome como "-") — última versão conhecida até o período.
    termos_comerciais = (
        db.query(StoreCommercialTerms)
        .filter(StoreCommercialTerms.cnpj_loja.in_(lojas_por_cnpj.keys()), StoreCommercialTerms.anomes <= f"{ano}{mes:02d}")
        .order_by(StoreCommercialTerms.anomes.desc())
        .all()
    )
    nome_por_cnpj: dict[str, str] = {}
    for termo in termos_comerciais:
        nome_por_cnpj.setdefault(termo.cnpj_loja, termo.loja)

    # 1) Contratos do mês (comissao_avista, nível contrato) — conta por loja e
    #    guarda os códigos de contrato pra cruzar com o financiamento (passo 2).
    contratos_mes = (
        db.query(Metric).filter(Metric.metric_name == "comissao_avista", Metric.metric_date == periodo).all()
    )
    contratos_por_cnpj: dict[str, list[str]] = {}
    for metric in contratos_mes:
        dims = metric.dimensions or {}
        cnpj = _extract_cnpj(dims.get("Lojista"))
        if cnpj not in lojas_por_cnpj:
            continue
        cd_contrato = dims.get("Cd Contrato")
        if cd_contrato:
            contratos_por_cnpj.setdefault(cnpj, []).append(str(cd_contrato))

    # 2) Valor financiado por contrato (digitacao_analitico, nível proposta) —
    #    igual ao XLOOKUP de VALOR_FINANCIAMENTO_R$ no base_final original.
    #    Janela ampla porque a proposta pode ter sido digitada meses antes da
    #    apuração da comissão fechar.
    todos_contratos = {c for lista in contratos_por_cnpj.values() for c in lista}
    valor_financiado_por_contrato: dict[str, float] = {}
    if todos_contratos:
        janela_inicio = periodo - relativedelta(months=6)
        janela_fim = periodo + relativedelta(months=1)
        propostas = (
            db.query(Metric)
            .filter(
                Metric.metric_name == "digitacao_analitico",
                Metric.metric_date >= janela_inicio,
                Metric.metric_date <= janela_fim,
            )
            .all()
        )
        for metric in propostas:
            cd_contrato = (metric.dimensions or {}).get("Cd Contrato")
            if cd_contrato and str(cd_contrato) in todos_contratos:
                valor_financiado_por_contrato[str(cd_contrato)] = _to_float(metric.value)

    # 3) Mercado (painel_visita_mercado) — produção C6, financiamento total do
    #    mercado e potencial (Financiamento Público Alvo, guardado como
    #    dimensão) do mês pedido e dos 2 meses fechados anteriores.
    meses_janela = [periodo, periodo - relativedelta(months=1), periodo - relativedelta(months=2)]
    mercado_metrics = (
        db.query(Metric)
        .filter(
            Metric.metric_name.in_(["mercado_producao_c6", "mercado_financiamento_total"]),
            Metric.metric_date.in_(meses_janela),
        )
        .all()
    )
    # cnpj -> mes -> {producao_c6, financiamento_total, potencial}
    mercado_por_cnpj_mes: dict[str, dict[date, dict[str, float]]] = {}
    for metric in mercado_metrics:
        dims = metric.dimensions or {}
        cnpj = _norm_cnpj(dims.get("CNPJ Loja"))
        if cnpj not in lojas_por_cnpj:
            continue
        bucket = mercado_por_cnpj_mes.setdefault(cnpj, {}).setdefault(metric.metric_date, {})
        if metric.metric_name == "mercado_producao_c6":
            bucket["producao_c6"] = _to_float(metric.value)
        else:
            bucket["financiamento_total"] = _to_float(metric.value)
            potencial = dims.get("Financiamento Público Alvo")
            if potencial is not None:
                # "Financiamento Público Alvo" ficou só como dimensão (nunca foi
                # promovida a `value`), então guarda o texto bruto do Looker, que
                # pode vir abreviado (ex.: "306.2 mil") — mesmo parsing usado no
                # RPA pra colunas de valor, não o `_to_float` simples daqui.
                bucket["potencial"] = parse_looker_number(potencial)

    lojas_out = []
    for cnpj, loja_cadastro in lojas_por_cnpj.items():
        contratos = contratos_por_cnpj.get(cnpj, [])
        producao_mes = sum(valor_financiado_por_contrato.get(c, 0.0) for c in contratos)

        # O relatório de mercado só consegue trazer o mês FECHADO mais recente
        # (ver rpa-conventions item 22 — {last_closed_month}), nunca o mês
        # corrente pedido em `periodo`. Por isso usamos o mês mais recente
        # disponível pra loja, não uma correspondência exata com `periodo` —
        # do contrário esses campos ficariam sempre `None` pra qualquer mês
        # "atual". O mês real é devolvido em `mercado_mes_referencia` pra quem
        # consome o dado saber que pode ser um mês antes do pedido.
        meses_dado = mercado_por_cnpj_mes.get(cnpj, {})
        mes_referencia = max(meses_dado.keys(), default=None)
        dado_referencia = meses_dado.get(mes_referencia, {}) if mes_referencia else {}
        potenciais = [m["potencial"] for m in meses_dado.values() if "potencial" in m]
        mercado_potencial_media_3m = sum(potenciais) / len(potenciais) if potenciais else None

        producao_c6_referencia = dado_referencia.get("producao_c6")
        financiamento_total_referencia = dado_referencia.get("financiamento_total")
        share_referencia = (
            producao_c6_referencia / financiamento_total_referencia
            if producao_c6_referencia is not None and financiamento_total_referencia
            else None
        )

        lojas_out.append(
            {
                "cnpj_loja": cnpj,
                "nome_loja": nome_por_cnpj.get(cnpj) or loja_cadastro.loja,
                "filial": loja_cadastro.filial,
                "loja_nova": loja_cadastro.loja_nova == "SIM",
                "qtd_contratos_mes": len(contratos),
                "producao_mes": round(producao_mes, 2),
                "mercado_potencial_media_3m": (
                    round(mercado_potencial_media_3m, 2) if mercado_potencial_media_3m is not None else None
                ),
                "mercado_mes_referencia": mes_referencia.isoformat() if mes_referencia else None,
                "mercado_producao_c6_mes_referencia": (
                    round(producao_c6_referencia, 2) if producao_c6_referencia is not None else None
                ),
                "mercado_financiamento_total_mes_referencia": (
                    round(financiamento_total_referencia, 2) if financiamento_total_referencia is not None else None
                ),
                "share_mes_referencia": round(share_referencia, 4) if share_referencia is not None else None,
            }
        )

    lojas_out.sort(key=lambda l: l["producao_mes"], reverse=True)
    return {"area": area, "ano": ano, "mes": mes, "lojas": lojas_out}
