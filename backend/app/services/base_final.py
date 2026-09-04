"""
Réplica linha-a-linha da aba `base_final` da planilha de controle do usuário
(ver skill `project-context`) — uma linha por contrato de `comissao_avista`,
cruzada com cadastro (Fase 1) e as demais métricas já ingeridas, incluindo o
cálculo completo de comissão do GN (Gerente de Negócios).

Diferente de `gn_dashboard.py` (Fase 2 — resumo por loja/área, só os números
de negócio), este módulo é a réplica FIEL da planilha original, coluna por
coluna, pedida explicitamente pelo usuário em 2026-09-04 pra ele conferir os
números direto contra o Excel. Onde a fórmula original tem uma inconsistência
conhecida (ver módulo `gn_dashboard.py`, item 1 do docstring — AREA_LOJA_EHS),
replicamos ela EXATAMENTE (não "corrigimos") — o objetivo aqui é comparação
célula a célula com o Excel, não uma versão "melhorada".

Pré-requisito: `comissao_avista` precisa ter sido ingerido DEPOIS que
`dimension_columns` foi ampliado pra cobrir todas as colunas de
`db_apuracaoavista` (ver `rpa-conventions`) — sem isso, os campos de
comissão/alçada/flags vêm `None` porque nunca foram baixados.
"""

import re
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.alcada_discount_rule import AlcadaDiscountRule
from app.models.commission_rate_tier import CommissionRateTier
from app.models.contract_override import ContractOverride
from app.models.gn_assignment import GnAssignment
from app.models.metric import Metric
from app.models.store_commercial_terms import StoreCommercialTerms
from app.models.store_registry_monthly import StoreRegistryMonthly
from app.services.connectors.base import parse_looker_number

_LOJISTA_CNPJ_RE = re.compile(r"^\s*\d+\s*-\s*(\d{14})\s*-")
# "28151 - CONC BH 4 - P" -> "CONC BH 4 - P" (código de filial + nome; só o
# nome bate com Filial/CARTERIZACAO_EHS do cadastro — ver rpa-conventions).
_FILIAL_CODE_PREFIX_RE = re.compile(r"^\s*\d+\s*-\s*(.+)$")


def _extract_cnpj(lojista: object) -> str | None:
    if not isinstance(lojista, str):
        return None
    match = _LOJISTA_CNPJ_RE.match(lojista)
    return match.group(1) if match else None


def _strip_filial_code(filial: object) -> str | None:
    if not isinstance(filial, str):
        return None
    match = _FILIAL_CODE_PREFIX_RE.match(filial)
    return match.group(1).strip() if match else filial.strip()


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _money(dims: dict, key: str) -> float | None:
    raw = dims.get(key)
    if raw is None:
        return None
    return parse_looker_number(raw)


def _percent(dims: dict, key: str) -> float | None:
    raw = dims.get(key)
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    texto = str(raw).replace("%", "").strip()
    if not texto or texto == "-":
        # Looker usa "-" (texto, não célula vazia) como "não se aplica" em campos
        # condicionais — ex.: "% Comissão Campanha Parceiro" quando o contrato não
        # tem campanha ativa (achado ao testar a carga histórica real 2026-09-04:
        # ~45% das linhas de db_apuracaoavista têm esse sentinel nesse campo
        # específico). Sem esse check, float("-") derruba a rota inteira pra
        # qualquer mês que tenha uma linha assim — mesma classe de bug do item 25
        # da skill rpa-conventions, mas com um sentinel de texto em vez de "%".
        return None
    return float(texto) / 100


def _text(dims: dict, key: str) -> str | None:
    raw = dims.get(key)
    return str(raw) if raw is not None else None


def get_base_final_rows(db: Session, ano: int, mes: int) -> list[dict]:
    periodo = date(ano, mes, 1)
    anomes = f"{ano}{mes:02d}"

    # 1) Contratos do mês — a linha-fato (uma por contrato).
    contratos = (
        db.query(Metric).filter(Metric.metric_name == "comissao_avista", Metric.metric_date == periodo).all()
    )
    if not contratos:
        return []

    codigos_contrato = {(m.dimensions or {}).get("Cd Contrato") for m in contratos}
    codigos_contrato.discard(None)

    # 2) Financiamento/data real da proposta (digitacao_analitico), casado por
    #    Cd Contrato — janela ampla porque a proposta pode ser anterior à
    #    apuração da comissão. Uma mesma proposta aparece VÁRIAS vezes em
    #    `digitacao_analitico` conforme avança de fase (ex.: "PROPOSTA
    #    APROVADA" -> "PROPOSTA PAGA", às vezes com Vl Financiamento levemente
    #    diferente entre as fases) — a fórmula original usa
    #    `XLOOKUP(Cd Contrato, ...)` SEM 6º argumento (search_mode), que
    #    default pra 1 = primeira ocorrência de cima pra baixo na planilha.
    #    Como `db_pagasanalitico` vem sempre em ordem cronológica ascendente
    #    (conferido linha a linha contra a planilha real do usuário, nenhuma
    #    data fora de ordem), "primeira ocorrência na planilha" equivale a
    #    "primeira proposta cronologicamente" — por isso ordena por
    #    (metric_date, created_at) ASC e mantém só a primeira vez que vê cada
    #    Cd Contrato. Pegar a ÚLTIMA (mais recente) em vez disso foi o bug real
    #    encontrado em produção 2026-09-04: batia por coincidência num dos 3
    #    campos checados pelo usuário mas divergia nos outros dois (ex.:
    #    Ago/26, Vl Financiamento saía R$ 22.464.978,49 em vez dos
    #    R$ 22.442.646,18 corretos).
    janela_inicio = periodo - relativedelta(months=6)
    janela_fim = periodo + relativedelta(months=1)
    propostas = (
        db.query(Metric)
        .filter(
            Metric.metric_name == "digitacao_analitico",
            Metric.metric_date >= janela_inicio,
            Metric.metric_date <= janela_fim,
        )
        .order_by(Metric.metric_date.asc(), Metric.created_at.asc())
        .all()
    )
    propostas_por_contrato: dict[str, Metric] = {}
    for p in propostas:
        cd = (p.dimensions or {}).get("Cd Contrato")
        if cd and str(cd) in codigos_contrato:
            propostas_por_contrato.setdefault(str(cd), p)

    # 3) Cadastro de loja (Fase 1) — termos comerciais (config_carteira), última
    #    versão conhecida por CNPJ, e carterização (área/GN) pelo mês exato.
    #
    #    NÃO filtra por `anomes <= período` (uma "modernização" tentada e
    #    revertida em 2026-09-04, ver histórico do modelo StoreCommercialTerms):
    #    a aba `config_carteira` de origem não é uma série mensal de verdade —
    #    é um cadastro de "estado atual conhecido" (487 de 522 linhas têm
    #    ANOMES do mês corrente, poucas linhas mais antigas nunca foram
    #    re-tocadas). Filtrar por período eliminava a ÚNICA linha de quase toda
    #    loja pra qualquer mês anterior ao atual, zerando Código Loja/Nome
    #    Loja/Grupo Loja/Cidade pra praticamente toda a base_final histórica
    #    (achado em produção: Ago/26 tinha 0 de 505 contratos com essas
    #    colunas preenchidas). Usa sempre o cadastro mais recente conhecido,
    #    igual ao XLOOKUP simples da planilha original (que também ignora
    #    período nessa aba).
    termos_por_cnpj: dict[str, StoreCommercialTerms] = {}
    for termo in db.query(StoreCommercialTerms).order_by(StoreCommercialTerms.anomes.asc()).all():
        termos_por_cnpj[termo.cnpj_loja] = termo  # mais recente sobrescreve

    carterizacao_por_chave: dict[str, StoreRegistryMonthly] = {}
    carterizacao_por_cnpj: dict[str, StoreRegistryMonthly] = {}
    for reg in (
        db.query(StoreRegistryMonthly)
        .filter(StoreRegistryMonthly.ano == ano, StoreRegistryMonthly.mes == mes)
        .all()
    ):
        if reg.chave_loja:
            carterizacao_por_chave[reg.chave_loja] = reg
        if reg.cnpj_loja:
            carterizacao_por_cnpj.setdefault(reg.cnpj_loja, reg)

    # 4) GN responsável por área/mês, e ajustes manuais de contrato (Fase 1).
    gn_por_area: dict[str, str] = {
        g.area: g.gn_responsavel
        for g in db.query(GnAssignment).filter(GnAssignment.ano == ano, GnAssignment.mes == mes).all()
    }
    override_por_contrato: dict[str, str] = {
        o.codigo_contrato: o.filial_ajustada for o in db.query(ContractOverride).all()
    }

    # 5) Desconto por alçada e faixas de comissão de GN (referência, tabelas
    #    pequenas — carregadas inteiras).
    desconto_por_alcada: dict[str, float] = {
        a.alcada: _to_float(a.desconto) for a in db.query(AlcadaDiscountRule).all()
    }
    tiers_por_produto: dict[str, CommissionRateTier] = {
        t.produto: t
        for t in db.query(CommissionRateTier).filter(CommissionRateTier.ano == ano, CommissionRateTier.mes == mes).all()
    }

    # 6) FATOR_META (% Ating. Ponderado Ajustado por filial, do bloco de metas
    #    por filial) — chave é o NOME da filial (sem o prefixo de código que
    #    esse relatório específico usa, ver `_strip_filial_code`).
    fator_meta_por_filial: dict[str, float] = {}
    for m in db.query(Metric).filter(Metric.metric_name == "producao_por_filial", Metric.metric_date == periodo).all():
        dims = m.dimensions or {}
        nome_filial = _strip_filial_code(dims.get("Filial"))
        # Vem como texto formatado do Looker (ex.: "150.0%"), igual aos outros
        # campos percentuais que ficam só como dimensão — usar _percent, não
        # _to_float (ver rpa-conventions item 25; achado em produção 2026-09-04
        # quando esse campo específico quebrou com ValueError).
        fator = _percent(dims, "% Ating. Ponderado Ajustado")
        if nome_filial and fator is not None:
            fator_meta_por_filial[nome_filial] = fator

    rows: list[dict] = []
    for contrato in contratos:
        dims = contrato.dimensions or {}
        cod_contrato = dims.get("Cd Contrato")
        cnpj_loja = _extract_cnpj(dims.get("Lojista"))
        termo = termos_por_cnpj.get(cnpj_loja) if cnpj_loja else None
        codigo_loja = termo.cd_loja if termo else None
        chave_loja = f"{ano}.{mes}.{cnpj_loja}.{codigo_loja}" if cnpj_loja and codigo_loja else None

        registro = carterizacao_por_chave.get(chave_loja) if chave_loja else None
        registro_fallback = carterizacao_por_cnpj.get(cnpj_loja) if cnpj_loja else None

        # AREA_LOJA_C6 e AREA_LOJA_EHS replicam a fórmula original tal como é,
        # inclusive a inconsistência dela (ver docstring do módulo): as duas
        # usam Filial como valor primário, e só EHS cai pra CARTERIZACAO_EHS
        # no fallback.
        if registro is not None:
            area_loja_c6 = registro.filial
            area_loja_ehs = registro.filial
        elif registro_fallback is not None:
            area_loja_c6 = registro_fallback.filial
            area_loja_ehs = registro_fallback.carterizacao_ehs
        else:
            area_loja_c6 = None
            area_loja_ehs = None

        gn_area_ehs = gn_por_area.get(area_loja_ehs) if area_loja_ehs else None

        filial_ajustada = override_por_contrato.get(cod_contrato) if cod_contrato else None
        if filial_ajustada:
            gn_contrato = gn_por_area.get(filial_ajustada, gn_area_ehs)
        else:
            gn_contrato = gn_area_ehs

        proposta = propostas_por_contrato.get(cod_contrato) if cod_contrato else None
        proposta_dims = (proposta.dimensions or {}) if proposta else {}
        data_financiamento = proposta.metric_date if proposta else None
        valor_financiamento = _to_float(proposta.value) if proposta else None
        valor_seguro_prestamista = _money(proposta_dims, "(R$) Seguro Prestamista")
        valor_seguro_ap = _money(proposta_dims, "(R$) Seguro AP")

        valor_principal = _money(dims, "R$ Principal Total")
        valor_comissionado_ehs = _money(dims, "R$ Principal Ajustado (TXE)")
        valor_seguro_total = _money(dims, "R$ Seguros Total")
        valor_seguro_outros = (
            valor_seguro_total - (valor_seguro_prestamista or 0) - (valor_seguro_ap or 0)
            if valor_seguro_total is not None
            else None
        )

        comissao_producao = _money(dims, "R$ Comissão Produção - Parceiro")
        # COMISSAO_SEGUROS_R$ vem de "R$ Comissão Produto - Parceiro" na
        # planilha original (base_final!AA = db_apuracaoavista!W) — parece
        # nome trocado na fonte (produto != seguros), mas é a fórmula real;
        # replicado assim de propósito, não temos motivo pra "corrigir" sem
        # confirmar com o usuário.
        comissao_seguros = _money(dims, "R$ Comissão Produto - Parceiro")
        comissao_pre_fator = (
            (comissao_producao or 0) + (comissao_seguros or 0)
            if comissao_producao is not None or comissao_seguros is not None
            else None
        )
        fator_ajuste_producao = _percent(dims, "% Fator Ajuste Produção")
        comissao_final = (
            comissao_pre_fator * fator_ajuste_producao
            if comissao_pre_fator is not None and fator_ajuste_producao is not None
            else None
        )
        comissao_final_pct = (
            comissao_final / valor_comissionado_ehs
            if comissao_final is not None and valor_comissionado_ehs
            else None
        )
        comissao_producao_pct = (
            comissao_producao / valor_comissionado_ehs
            if comissao_producao is not None and valor_comissionado_ehs
            else None
        )
        comissao_seguro_pct = (
            comissao_seguros / valor_comissionado_ehs
            if comissao_seguros is not None and valor_comissionado_ehs
            else 0.0
        )

        alcada_real = _text(dims, "Tp Alcada")
        alcada_ehs = _text(dims, "Tp Alcada Considerada")
        desconto_ehs = (
            valor_comissionado_ehs / valor_principal - 1
            if valor_comissionado_ehs is not None and valor_principal
            else None
        )
        desconto_gn = desconto_por_alcada.get(alcada_real)
        producao_comissionada_gn = (
            valor_principal * (1 + desconto_gn) if valor_principal is not None and desconto_gn is not None else None
        )

        produto = _text(dims, "Produto")
        fator_meta = fator_meta_por_filial.get(area_loja_ehs) if area_loja_ehs else None
        tier = tiers_por_produto.get(produto) if produto else None
        comissao_gn_pct = None
        if tier is not None and fator_meta is not None:
            if fator_meta >= 1.2:
                comissao_gn_pct = _to_float(tier.comissao_acima_120)
            elif fator_meta >= 1.0:
                comissao_gn_pct = _to_float(tier.comissao_100_119)
            else:
                comissao_gn_pct = _to_float(tier.comissao_abaixo_100)
        comissao_gn_valor = (
            comissao_gn_pct * producao_comissionada_gn
            if comissao_gn_pct is not None and producao_comissionada_gn is not None
            else None
        )

        id_spf = _text(dims, "Fg Spf")
        id_spp = _text(dims, "Fg Spp")
        id_carglass = _text(dims, "Fg Carglass")
        id_seguro = "SIM" if "SIM" in (id_spf, id_spp, id_carglass) else "NÃO"

        rows.append(
            {
                "ano": ano,
                "mes": mes,
                "data_financiamento": data_financiamento.isoformat() if data_financiamento else None,
                "chave_area": f"{ano}.{mes}.{area_loja_ehs}" if area_loja_ehs else None,
                "area_loja_c6": area_loja_c6,
                "area_loja_ehs": area_loja_ehs,
                "gn_area_ehs": gn_area_ehs,
                "cidade_loja": termo.cidade if termo else None,
                "chave_loja": chave_loja,
                "cnpj_loja": cnpj_loja,
                "codigo_loja": codigo_loja,
                "nome_loja": termo.loja if termo else None,
                "grupo_loja": termo.grupo_loja if termo else None,
                "cod_contrato": cod_contrato,
                "status_contrato": _text(dims, "Status Contrato"),
                "produto": produto,
                "gn_contrato": gn_contrato,
                "valor_financiamento": valor_financiamento,
                "valor_principal": valor_principal,
                "valor_comissionado_ehs": valor_comissionado_ehs,
                "valor_seguro_total": valor_seguro_total,
                "valor_seguro_prestamista": valor_seguro_prestamista,
                "valor_seguro_ap": valor_seguro_ap,
                "valor_seguro_outros": valor_seguro_outros,
                "comissao_final": comissao_final,
                "comissao_pre_fator": comissao_pre_fator,
                "comissao_producao": comissao_producao,
                "comissao_seguros": comissao_seguros,
                "comissao_final_pct": comissao_final_pct,
                "comissao_producao_pct": comissao_producao_pct,
                "comissao_produto_pct": _percent(dims, "% Comissão Produção Parceiro"),
                "comissao_campanha_pct": _percent(dims, "% Comissão Campanha Parceiro"),
                "comissao_seguro_pct": comissao_seguro_pct,
                "alcada_real": alcada_real,
                "alcada_ehs": alcada_ehs,
                "desconto_ehs": desconto_ehs,
                "desconto_gn": desconto_gn,
                "producao_comissionada_gn": producao_comissionada_gn,
                "fator_meta": fator_meta,
                "comissao_gn_pct": comissao_gn_pct,
                "comissao_gn_valor": comissao_gn_valor,
                "id_carteira_ajustada": "SIM" if area_loja_c6 != area_loja_ehs else "NÃO",
                "id_gn_alterado": "SIM" if gn_contrato != gn_area_ehs else "NÃO",
                "id_seguro": id_seguro,
                "id_spf": id_spf,
                "id_spp": id_spp,
                "id_carglass": id_carglass,
                "id_lojanova": _text(dims, "Loja Nova"),
                "id_parceironovo": _text(dims, "Parceiro Novo"),
                "id_campanha": _text(dims, "Campanha"),
                "id_taxa": _text(dims, "Possui TXE?"),
                "id_balde": _text(dims, "Aplicação balde?"),
            }
        )

    return rows
