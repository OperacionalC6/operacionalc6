"""
Importação das tabelas de cadastro/config (Fase 1 do dashboard de comissão de
GN — ver skill `project-context`): dado que o usuário mantém manualmente numa
planilha (não vem do Looker/RPA), carregado aqui a partir de um arquivo
Excel/CSV.

Cada tabela é um cadastro/referência, não um evento — por isso a importação
SUBSTITUI o conteúdo inteiro da tabela a cada upload (não faz upsert linha a
linha: mais simples e evita registro órfão de uma versão antiga da planilha).
Mesmo padrão de "apagar e reinserir" já usado em `pipeline.run_pipeline()`
para a tabela `metrics`.
"""

import logging
import math

import pandas as pd
from sqlalchemy.orm import Session

from app.models.alcada_discount_rule import AlcadaDiscountRule
from app.models.commission_rate_tier import CommissionRateTier
from app.models.contract_override import ContractOverride
from app.models.gn_assignment import GnAssignment
from app.models.store_commercial_terms import StoreCommercialTerms
from app.models.store_registry_monthly import StoreRegistryMonthly

logger = logging.getLogger(__name__)


def _clean_str(value: object) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    if isinstance(value, float) and value.is_integer():
        # CNPJ/código de loja vêm como float (ex.: 49359667000174.0) quando a coluna
        # do Excel tem valor numérico misturado com texto em outras linhas.
        return str(int(value))
    return str(value)


def _clean_int(value: object) -> int | None:
    text = _clean_str(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _clean_numeric(value: object) -> float | None:
    text = _clean_str(value)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def import_store_registry_monthly(db: Session, df: pd.DataFrame) -> int:
    """`db_carterizacao`: histórico mês a mês de área/GN/GP por loja."""
    db.query(StoreRegistryMonthly).delete(synchronize_session=False)
    count = 0
    for _, row in df.iterrows():
        chave_loja = _clean_str(row.get("CHAVE_LOJA"))
        ano = _clean_int(row.get("ANO"))
        mes = _clean_int(row.get("MES"))
        anomes = _clean_str(row.get("Anomes"))
        if not chave_loja or ano is None or mes is None or not anomes:
            continue
        db.add(
            StoreRegistryMonthly(
                ano=ano,
                mes=mes,
                anomes=anomes,
                chave_loja=chave_loja,
                cnpj_loja=_clean_str(row.get("Cnpj Da Loja")),
                carterizacao_ehs=_clean_str(row.get("CARTERIZACAO_EHS")),
                cd_loja=_clean_str(row.get("Cd Loja")),
                loja=_clean_str(row.get("Loja")),
                loja_nova=_clean_str(row.get("Loja Nova")),
                cidade=_clean_str(row.get("Cidade")),
                rede=_clean_str(row.get("Rede")),
                regional=_clean_str(row.get("Regional")),
                filial=_clean_str(row.get("Filial")),
                gp=_clean_str(row.get("GP")),
                gn=_clean_str(row.get("GN")),
                gn_backup=_clean_str(row.get("GN Backup")),
                atendimento=_clean_str(row.get("Atendimento")),
                classificacao=_clean_str(row.get("Classificação")),
                shopping=_clean_str(row.get("Shopping")),
                concessionaria=_clean_str(row.get("Concessionária")),
                mercado=_clean_numeric(row.get("Mercado")),
                retorno=_clean_numeric(row.get("Retorno")),
                acordo=_clean_numeric(row.get("Acordo")),
                comissao_seguros=_clean_numeric(row.get("Comissão Seguros")),
                parceiro_atendimento=_clean_str(row.get("Parceiro Atendimento")),
                master=_clean_str(row.get("Master")),
            )
        )
        count += 1
    return count


def import_store_commercial_terms(db: Session, df: pd.DataFrame) -> int:
    """`config_carteira`: identidade/termos comerciais da loja por CNPJ."""
    db.query(StoreCommercialTerms).delete(synchronize_session=False)
    count = 0
    for _, row in df.iterrows():
        cnpj_loja = _clean_str(row.get("CNPJ DA LOJA"))
        anomes = _clean_str(row.get("ANOMES"))
        if not cnpj_loja or not anomes:
            continue
        db.add(
            StoreCommercialTerms(
                cnpj_loja=cnpj_loja,
                anomes=anomes,
                carteira_ajustada=_clean_str(row.get("CARTEIRA_AJUSTADA")),
                raiz_cnpj=_clean_str(row.get("RAIZ_CNPJ")),
                cd_loja=_clean_str(row.get("CD LOJA")),
                loja=_clean_str(row.get("LOJA")),
                grupo_loja=_clean_str(row.get("GRUPO_LOJA")),
                bandeira_principal=_clean_str(row.get("BANDEIRA_PRINCIPAL")),
                subsegmento=_clean_str(row.get("SUBSEGMENTO")),
                filial=_clean_str(row.get("FILIAL")),
                regional=_clean_str(row.get("REGIONAL")),
                rede=_clean_str(row.get("REDE")),
                mercado=_clean_numeric(row.get("MERCADO")),
                retorno=_clean_numeric(row.get("RETORNO")),
                acordo=_clean_numeric(row.get("ACORDO")),
                comissao_seguros=_clean_numeric(row.get("COMISSÃO SEGUROS")),
                classificacao=_clean_str(row.get("CLASSIFICAÇÃO")),
                estado=_clean_str(row.get("ESTADO")),
                cidade=_clean_str(row.get("CIDADE")),
                bairro=_clean_str(row.get("BAIRRO")),
                endereco=_clean_str(row.get("ENDERECO")),
                loja_nova=_clean_str(row.get("LOJA NOVA")),
                atendimento=_clean_str(row.get("ATENDIMENTO")),
                shopping=_clean_str(row.get("SHOPPING")),
                concessionaria=_clean_str(row.get("CONCESSIONÁRIA")),
                parceiro_atendimento=_clean_str(row.get("PARCEIRO ATENDIMENTO")),
                master=_clean_str(row.get("MASTER")),
                retorno_max=_clean_str(row.get("RETORNO MÁX")),
                retorno_default=_clean_str(row.get("RETORNO_DEFAULT")),
                tipo_limitacao=_clean_str(row.get("TIPO LIMITAÇÃO")),
            )
        )
        count += 1
    return count


def import_gn_assignments(db: Session, df: pd.DataFrame) -> int:
    """`config_GNs`: GN responsável por área, mês a mês."""
    db.query(GnAssignment).delete(synchronize_session=False)
    count = 0
    for _, row in df.iterrows():
        area = _clean_str(row.get("AREA"))
        ano = _clean_int(row.get("ANO"))
        mes = _clean_int(row.get("MES"))
        gn_responsavel = _clean_str(row.get("GN_RESPONSAVEL"))
        if not area or ano is None or mes is None or not gn_responsavel:
            continue
        db.add(GnAssignment(area=area, ano=ano, mes=mes, gn_responsavel=gn_responsavel))
        count += 1
    return count


def import_commission_rate_tiers(db: Session, df: pd.DataFrame) -> int:
    """`config_remuneracao`: % de comissão do GN por produto e faixa de atingimento."""
    db.query(CommissionRateTier).delete(synchronize_session=False)
    count = 0
    # A coluna "Produto" real (nome do produto) vem duplicada com a coluna-chave
    # "Produto" (concatenação produto.ano.mes usada só na planilha) — pandas
    # renomeia a segunda ocorrência para "Produto.1" ao ler o Excel.
    produto_col = "Produto.1" if "Produto.1" in df.columns else "Produto"
    for _, row in df.iterrows():
        produto = _clean_str(row.get(produto_col))
        ano = _clean_int(row.get("ANO"))
        mes = _clean_int(row.get("MES"))
        abaixo_100 = _clean_numeric(row.get("%Comissão\n<100%"))
        cem_119 = _clean_numeric(row.get("%Comissão\n100-119%"))
        acima_120 = _clean_numeric(row.get("%Comissão\n>120%"))
        if not produto or ano is None or mes is None or abaixo_100 is None or cem_119 is None or acima_120 is None:
            continue
        db.add(
            CommissionRateTier(
                produto=produto,
                ano=ano,
                mes=mes,
                comissao_abaixo_100=abaixo_100,
                comissao_100_119=cem_119,
                comissao_acima_120=acima_120,
            )
        )
        count += 1
    return count


def import_alcada_discount_rules(db: Session, df: pd.DataFrame) -> int:
    """`config_regras_alcada`: desconto por tipo de alçada."""
    db.query(AlcadaDiscountRule).delete(synchronize_session=False)
    count = 0
    for _, row in df.iterrows():
        alcada = _clean_str(row.get("Alçada Taxa Especial"))
        desconto = _clean_numeric(row.get("DESCONTO"))
        if not alcada or desconto is None:
            continue
        db.add(AlcadaDiscountRule(alcada=alcada, desconto=desconto))
        count += 1
    return count


def import_contract_overrides(db: Session, df: pd.DataFrame) -> int:
    """`config_AjustesContrato`: ajuste manual de filial por contrato (só as 2
    colunas de entrada real — o resto da aba original é fórmula derivada)."""
    db.query(ContractOverride).delete(synchronize_session=False)
    count = 0
    for _, row in df.iterrows():
        codigo_contrato = _clean_str(row.get("Codigo Contrato"))
        filial_ajustada = _clean_str(row.get("FILIAL_AJUSTADA"))
        if not codigo_contrato or not filial_ajustada:
            continue
        db.add(ContractOverride(codigo_contrato=codigo_contrato, filial_ajustada=filial_ajustada))
        count += 1
    return count
