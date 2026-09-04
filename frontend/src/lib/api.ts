"use client";

import { API_BASE_URL } from "./config";
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "./auth";
import type { BaseFinalRow, GnAreaScorecard, Metric, User } from "./types";

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) return false;

  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return true;
}

async function apiFetch<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  const accessToken = getAccessToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });

  if (res.status === 401 && !retried) {
    const refreshed = await refreshAccessToken();
    if (refreshed) return apiFetch<T>(path, init, true);
    clearTokens();
    throw new ApiError(401, "Sessão expirada. Faça login novamente.");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail ?? `Erro na requisição (${res.status}).`);
  }

  return res.json() as Promise<T>;
}

export async function loginWithGoogle(idToken: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail ?? "Falha ao entrar com Google.");
  }

  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
}

export function fetchMe(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

export function fetchMetrics(params?: {
  date_from?: string;
  date_to?: string;
  metric_name?: string;
}): Promise<Metric[]> {
  const query = new URLSearchParams();
  if (params?.date_from) query.set("date_from", params.date_from);
  if (params?.date_to) query.set("date_to", params.date_to);
  if (params?.metric_name) query.set("metric_name", params.metric_name);
  const qs = query.toString();
  return apiFetch<Metric[]>(`/metrics${qs ? `?${qs}` : ""}`);
}

export function fetchGnAreas(ano: number, mes: number): Promise<string[]> {
  const query = new URLSearchParams({ ano: String(ano), mes: String(mes) });
  return apiFetch<string[]>(`/gn-dashboard/areas?${query.toString()}`);
}

export function fetchGnAreaScorecard(
  area: string,
  ano: number,
  mes: number
): Promise<GnAreaScorecard> {
  const query = new URLSearchParams({ area, ano: String(ano), mes: String(mes) });
  return apiFetch<GnAreaScorecard>(`/gn-dashboard/area-scorecard?${query.toString()}`);
}

export function fetchBaseFinal(ano: number, mes: number, area?: string): Promise<BaseFinalRow[]> {
  const query = new URLSearchParams({ ano: String(ano), mes: String(mes) });
  if (area) query.set("area", area);
  return apiFetch<BaseFinalRow[]>(`/gn-dashboard/base-final?${query.toString()}`);
}

export { ApiError };
