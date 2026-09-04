export type UserRole = "admin" | "gestor" | "membro";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  team_id: string | null;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Metric {
  id: string;
  team_id: string | null;
  metric_date: string;
  metric_name: string;
  value: number;
  dimensions: Record<string, unknown> | null;
  source: string;
  created_at: string;
}

export interface GnScorecardLoja {
  cnpj_loja: string;
  nome_loja: string | null;
  filial: string | null;
  loja_nova: boolean;
  qtd_contratos_mes: number;
  producao_mes: number;
  mercado_potencial_media_3m: number | null;
  mercado_mes_referencia: string | null;
  mercado_producao_c6_mes_referencia: number | null;
  mercado_financiamento_total_mes_referencia: number | null;
  share_mes_referencia: number | null;
}

export interface GnAreaScorecard {
  area: string;
  ano: number;
  mes: number;
  lojas: GnScorecardLoja[];
}

// Réplica linha-a-linha da aba base_final da planilha do usuário — uma linha
// por contrato. Espelha exatamente as chaves de app/services/base_final.py.
export interface BaseFinalRow {
  ano: number;
  mes: number;
  data_financiamento: string | null;
  chave_area: string | null;
  area_loja_c6: string | null;
  area_loja_ehs: string | null;
  gn_area_ehs: string | null;
  cidade_loja: string | null;
  chave_loja: string | null;
  cnpj_loja: string | null;
  codigo_loja: string | null;
  nome_loja: string | null;
  grupo_loja: string | null;
  cod_contrato: string | null;
  status_contrato: string | null;
  produto: string | null;
  gn_contrato: string | null;
  valor_financiamento: number | null;
  valor_principal: number | null;
  valor_comissionado_ehs: number | null;
  valor_seguro_total: number | null;
  valor_seguro_prestamista: number | null;
  valor_seguro_ap: number | null;
  valor_seguro_outros: number | null;
  comissao_final: number | null;
  comissao_pre_fator: number | null;
  comissao_producao: number | null;
  comissao_seguros: number | null;
  comissao_final_pct: number | null;
  comissao_producao_pct: number | null;
  comissao_produto_pct: number | null;
  comissao_campanha_pct: number | null;
  comissao_seguro_pct: number | null;
  alcada_real: string | null;
  alcada_ehs: string | null;
  desconto_ehs: number | null;
  desconto_gn: number | null;
  producao_comissionada_gn: number | null;
  fator_meta: number | null;
  comissao_gn_pct: number | null;
  comissao_gn_valor: number | null;
  id_carteira_ajustada: string | null;
  id_gn_alterado: string | null;
  id_seguro: string | null;
  id_spf: string | null;
  id_spp: string | null;
  id_carglass: string | null;
  id_lojanova: string | null;
  id_parceironovo: string | null;
  id_campanha: string | null;
  id_taxa: string | null;
  id_balde: string | null;
}
