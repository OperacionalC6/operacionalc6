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
