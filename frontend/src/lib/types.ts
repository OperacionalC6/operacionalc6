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
