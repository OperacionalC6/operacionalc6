"use client";

/* eslint-disable react-hooks/set-state-in-effect --
 * Mesmo caso de /dashboard/gn: reseta loading/erro ao reagir a mudança de
 * ano/mês antes de rebuscar dado novo, igual ao exemplo oficial de
 * "fetching data" do react.dev. Ver justificativa completa naquele arquivo.
 */

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, fetchBaseFinal, fetchMe } from "@/lib/api";
import { clearTokens, isLoggedIn } from "@/lib/auth";
import { MESES } from "@/lib/dates";
import type { BaseFinalRow, User } from "@/lib/types";

type ColFormat = "text" | "date" | "currency" | "percent" | "number";

interface ColumnDef {
  key: keyof BaseFinalRow;
  label: string;
  group: string;
  format: ColFormat;
}

// Mesmos grupos de coluna da linha 1 do cabeçalho do base_final original
// (DATA, LOJA, CONTRATO, VALOR_FINANC, VALOR_SEGURO, COMISSAO_EHS, TAXA,
// COMISSAO_GNS, IDS) — pra ficar reconhecível pra quem já usa a planilha.
const COLUMNS: ColumnDef[] = [
  { key: "ano", label: "Ano", group: "Data", format: "number" },
  { key: "mes", label: "Mês", group: "Data", format: "number" },
  { key: "data_financiamento", label: "Dt Financiamento", group: "Data", format: "date" },
  { key: "area_loja_c6", label: "Área (C6)", group: "Loja", format: "text" },
  { key: "area_loja_ehs", label: "Área (EHS)", group: "Loja", format: "text" },
  { key: "gn_area_ehs", label: "GN Área", group: "Loja", format: "text" },
  { key: "cidade_loja", label: "Cidade", group: "Loja", format: "text" },
  { key: "cnpj_loja", label: "CNPJ Loja", group: "Loja", format: "text" },
  { key: "codigo_loja", label: "Código Loja", group: "Loja", format: "text" },
  { key: "nome_loja", label: "Nome Loja", group: "Loja", format: "text" },
  { key: "grupo_loja", label: "Grupo Loja", group: "Loja", format: "text" },
  { key: "cod_contrato", label: "Cód. Contrato", group: "Contrato", format: "text" },
  { key: "status_contrato", label: "Status", group: "Contrato", format: "text" },
  { key: "produto", label: "Produto", group: "Contrato", format: "text" },
  { key: "gn_contrato", label: "GN Contrato", group: "Contrato", format: "text" },
  { key: "valor_financiamento", label: "Vl Financiamento", group: "Vl Financ.", format: "currency" },
  { key: "valor_principal", label: "Vl Principal", group: "Vl Financ.", format: "currency" },
  { key: "valor_comissionado_ehs", label: "Vl Comissionado EHS", group: "Vl Financ.", format: "currency" },
  { key: "valor_seguro_total", label: "Vl Seguro Total", group: "Vl Seguro", format: "currency" },
  { key: "valor_seguro_prestamista", label: "Vl Seguro Prestamista", group: "Vl Seguro", format: "currency" },
  { key: "valor_seguro_ap", label: "Vl Seguro AP", group: "Vl Seguro", format: "currency" },
  { key: "valor_seguro_outros", label: "Vl Seguro Outros", group: "Vl Seguro", format: "currency" },
  { key: "comissao_final", label: "Comissão Final R$", group: "Comissão EHS", format: "currency" },
  { key: "comissao_pre_fator", label: "Comissão Pré-Fator R$", group: "Comissão EHS", format: "currency" },
  { key: "comissao_producao", label: "Comissão Produção R$", group: "Comissão EHS", format: "currency" },
  { key: "comissao_seguros", label: "Comissão Seguros R$", group: "Comissão EHS", format: "currency" },
  { key: "comissao_final_pct", label: "Comissão Final %", group: "Comissão EHS", format: "percent" },
  { key: "comissao_producao_pct", label: "Comissão Produção %", group: "Comissão EHS", format: "percent" },
  { key: "comissao_produto_pct", label: "Comissão Produto %", group: "Comissão EHS", format: "percent" },
  { key: "comissao_campanha_pct", label: "Comissão Campanha %", group: "Comissão EHS", format: "percent" },
  { key: "comissao_seguro_pct", label: "Comissão Seguro %", group: "Comissão EHS", format: "percent" },
  { key: "alcada_real", label: "Alçada Real", group: "Taxa", format: "text" },
  { key: "alcada_ehs", label: "Alçada EHS", group: "Taxa", format: "text" },
  { key: "desconto_ehs", label: "Desconto EHS", group: "Taxa", format: "percent" },
  { key: "desconto_gn", label: "Desconto GN", group: "Taxa", format: "percent" },
  { key: "producao_comissionada_gn", label: "Produção Comis. GN", group: "Comissão GN", format: "currency" },
  { key: "fator_meta", label: "Fator Meta", group: "Comissão GN", format: "percent" },
  { key: "comissao_gn_pct", label: "Comissão GN %", group: "Comissão GN", format: "percent" },
  { key: "comissao_gn_valor", label: "Comissão GN R$", group: "Comissão GN", format: "currency" },
  { key: "id_carteira_ajustada", label: "Carteira Ajustada", group: "IDs", format: "text" },
  { key: "id_gn_alterado", label: "GN Alterado", group: "IDs", format: "text" },
  { key: "id_seguro", label: "Tem Seguro", group: "IDs", format: "text" },
  { key: "id_spf", label: "SPF", group: "IDs", format: "text" },
  { key: "id_spp", label: "SPP", group: "IDs", format: "text" },
  { key: "id_carglass", label: "Carglass", group: "IDs", format: "text" },
  { key: "id_lojanova", label: "Loja Nova", group: "IDs", format: "text" },
  { key: "id_parceironovo", label: "Parceiro Novo", group: "IDs", format: "text" },
  { key: "id_campanha", label: "Campanha", group: "IDs", format: "text" },
  { key: "id_taxa", label: "Possui TXE", group: "IDs", format: "text" },
  { key: "id_balde", label: "Balde", group: "IDs", format: "text" },
];

function formatCell(value: unknown, format: ColFormat): string {
  if (value === null || value === undefined || value === "") return "—";
  switch (format) {
    case "currency":
      return Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    case "percent":
      return Number(value).toLocaleString("pt-BR", { style: "percent", minimumFractionDigits: 1 });
    case "date":
      return new Date(`${value}T00:00:00`).toLocaleDateString("pt-BR");
    case "number":
      return String(value);
    default:
      return String(value);
  }
}

type SortDirection = "asc" | "desc";
interface SortState {
  key: keyof BaseFinalRow;
  direction: SortDirection;
}

export default function BaseFinalPage() {
  const router = useRouter();
  const hoje = new Date();

  const [user, setUser] = useState<User | null>(null);
  const [ano, setAno] = useState(hoje.getFullYear());
  const [mes, setMes] = useState(hoje.getMonth() + 1);
  const [rows, setRows] = useState<BaseFinalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Partial<Record<keyof BaseFinalRow, string>>>({});
  const [sort, setSort] = useState<SortState | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/");
      return;
    }

    setLoading(true);
    setError(null);
    Promise.all([fetchMe(), fetchBaseFinal(ano, mes)])
      .then(([meData, rowsData]) => {
        setUser(meData);
        setRows(rowsData);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erro ao carregar base_final.");
        setRows([]);
      })
      .finally(() => setLoading(false));
  }, [ano, mes, router]);

  function handleLogout() {
    clearTokens();
    router.replace("/");
  }

  function handleFilterChange(key: keyof BaseFinalRow, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  function handleSortClick(key: keyof BaseFinalRow) {
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, direction: "asc" };
      if (prev.direction === "asc") return { key, direction: "desc" };
      return null;
    });
  }

  // Valores distintos por coluna (pro filtro-dropdown de colunas categóricas
  // — texto e data). Calculado sobre TODAS as linhas do período, não sobre o
  // resultado já filtrado — os dropdowns não fazem cascata entre si.
  const distinctValues = useMemo(() => {
    const map = {} as Record<keyof BaseFinalRow, string[]>;
    for (const col of COLUMNS) {
      if (col.format !== "text" && col.format !== "date") continue;
      const set = new Set<string>();
      for (const row of rows) {
        const v = row[col.key];
        if (v !== null && v !== undefined && v !== "") set.add(String(v));
      }
      map[col.key] = Array.from(set).sort((a, b) => a.localeCompare(b, "pt-BR"));
    }
    return map;
  }, [rows]);

  const filteredSortedRows = useMemo(() => {
    const activeFilters = Object.entries(filters).filter(([, v]) => v && v.trim() !== "");

    let result = rows;
    if (activeFilters.length > 0) {
      result = rows.filter((row) =>
        activeFilters.every(([key, filterValue]) => {
          const col = COLUMNS.find((c) => c.key === key);
          const display = formatCell(row[key as keyof BaseFinalRow], col?.format ?? "text");
          return display.toLowerCase().includes(filterValue.trim().toLowerCase());
        })
      );
    }

    if (sort) {
      const col = COLUMNS.find((c) => c.key === sort.key);
      const isNumeric = col?.format === "currency" || col?.format === "percent" || col?.format === "number";
      result = [...result].sort((a, b) => {
        const va = a[sort.key];
        const vb = b[sort.key];
        if (va === null && vb === null) return 0;
        if (va === null) return 1;
        if (vb === null) return -1;
        let cmp: number;
        if (isNumeric) {
          cmp = Number(va) - Number(vb);
        } else {
          cmp = String(va).localeCompare(String(vb), "pt-BR");
        }
        return sort.direction === "asc" ? cmp : -cmp;
      });
    }

    return result;
  }, [rows, filters, sort]);

  // Subtotal por coluna (reage aos filtros ativos, igual SUBTOTAL() do Excel
  // com autofiltro): soma pra colunas numéricas (com valor), contagem de
  // linhas preenchidas pra colunas de texto/data (sem valor).
  const subtotals = useMemo(() => {
    const result = {} as Record<keyof BaseFinalRow, number>;
    for (const col of COLUMNS) {
      const isNumeric = col.format === "currency" || col.format === "percent" || col.format === "number";
      if (isNumeric) {
        result[col.key] = filteredSortedRows.reduce((sum, row) => {
          const v = row[col.key];
          return v !== null && v !== undefined ? sum + Number(v) : sum;
        }, 0);
      } else {
        result[col.key] = filteredSortedRows.filter((row) => {
          const v = row[col.key];
          return v !== null && v !== undefined && v !== "";
        }).length;
      }
    }
    return result;
  }, [filteredSortedRows]);

  // Cabeçalho agrupado (2 linhas, igual à planilha original): calcula quantas
  // colunas seguidas pertencem ao mesmo grupo pra usar colSpan.
  const groupSpans = useMemo(() => {
    const spans: { group: string; span: number }[] = [];
    for (const col of COLUMNS) {
      const last = spans[spans.length - 1];
      if (last && last.group === col.group) {
        last.span += 1;
      } else {
        spans.push({ group: col.group, span: 1 });
      }
    }
    return spans;
  }, []);

  return (
    <div className="flex flex-1 flex-col bg-zinc-50">
      <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900">base_final — contrato a contrato</h1>
          {user && (
            <p className="text-sm text-zinc-500">
              {user.full_name} · {user.role}
            </p>
          )}
        </div>
        <div className="flex items-center gap-4">
          <Link href="/dashboard/gn" className="text-sm text-zinc-600 hover:text-zinc-900">
            Comissão por área
          </Link>
          <Link href="/dashboard" className="text-sm text-zinc-600 hover:text-zinc-900">
            ← Visão geral
          </Link>
          <button
            onClick={handleLogout}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-100"
          >
            Sair
          </button>
        </div>
      </header>

      <main className="flex-1 px-6 py-6">
        <div className="mb-4 flex flex-wrap items-end gap-4">
          <label className="flex flex-col text-sm text-zinc-600">
            Mês
            <select
              value={mes}
              onChange={(e) => setMes(Number(e.target.value))}
              className="mt-1 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-zinc-900"
            >
              {MESES.map((nome, i) => (
                <option key={nome} value={i + 1}>
                  {nome}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col text-sm text-zinc-600">
            Ano
            <input
              type="number"
              value={ano}
              onChange={(e) => setAno(Number(e.target.value))}
              className="mt-1 w-24 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-zinc-900"
            />
          </label>

          <p className="pb-1.5 text-sm text-zinc-500">
            {loading ? "Carregando..." : `${filteredSortedRows.length} de ${rows.length} contratos`}
          </p>
        </div>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        {!error && (
          <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white">
            <div className="max-h-[75vh] overflow-auto">
              <table className="w-full border-collapse text-xs">
                <thead className="sticky top-0 z-10 bg-zinc-50">
                  <tr>
                    {groupSpans.map(({ group, span }) => (
                      <th
                        key={group}
                        colSpan={span}
                        className="border-b border-zinc-200 px-2 py-1 text-left font-semibold text-zinc-500"
                      >
                        {group}
                      </th>
                    ))}
                  </tr>
                  <tr>
                    {COLUMNS.map((col) => (
                      <th
                        key={col.key}
                        className="whitespace-nowrap border-b border-zinc-200 px-2 py-1 text-left font-medium text-zinc-700"
                      >
                        <button
                          onClick={() => handleSortClick(col.key)}
                          className="flex items-center gap-1 hover:text-zinc-900"
                          title="Clique pra ordenar"
                        >
                          {col.label}
                          {sort?.key === col.key && <span>{sort.direction === "asc" ? "▲" : "▼"}</span>}
                        </button>
                        {col.format === "text" || col.format === "date" ? (
                          <select
                            value={filters[col.key] ?? ""}
                            onChange={(e) => handleFilterChange(col.key, e.target.value)}
                            className="mt-1 w-full rounded border border-zinc-200 px-1 py-0.5 text-xs font-normal text-zinc-700"
                          >
                            <option value="">(Todos)</option>
                            {(distinctValues[col.key] ?? []).map((v) => {
                              // O filtro compara contra o texto JÁ FORMATADO da célula
                              // (ver `filteredSortedRows`), então a opção do dropdown
                              // precisa usar o mesmo texto formatado como valor —
                              // senão data ISO ("2026-08-15") nunca bate com o exibido
                              // na tabela ("15/08/2026").
                              const display = col.format === "date" ? formatCell(v, "date") : v;
                              return (
                                <option key={v} value={display}>
                                  {display}
                                </option>
                              );
                            })}
                          </select>
                        ) : (
                          <input
                            type="text"
                            value={filters[col.key] ?? ""}
                            onChange={(e) => handleFilterChange(col.key, e.target.value)}
                            placeholder="filtrar..."
                            className="mt-1 w-full rounded border border-zinc-200 px-1 py-0.5 text-xs font-normal text-zinc-700"
                          />
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {!loading && filteredSortedRows.length === 0 && (
                    <tr>
                      <td colSpan={COLUMNS.length} className="px-4 py-8 text-center text-zinc-400">
                        Nenhum contrato encontrado pra esse período/filtro.
                      </td>
                    </tr>
                  )}
                  {filteredSortedRows.map((row, i) => (
                    <tr key={`${row.cod_contrato}-${i}`} className="border-b border-zinc-100 hover:bg-zinc-50">
                      {COLUMNS.map((col) => (
                        <td key={col.key} className="whitespace-nowrap px-2 py-1 text-zinc-700">
                          {formatCell(row[col.key], col.format)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
                {filteredSortedRows.length > 0 && (
                  <tfoot className="sticky bottom-0 z-10 bg-zinc-100 font-semibold">
                    <tr>
                      {COLUMNS.map((col, i) => {
                        const isNumeric =
                          col.format === "currency" || col.format === "percent" || col.format === "number";
                        const value = subtotals[col.key];
                        return (
                          <td key={col.key} className="whitespace-nowrap border-t-2 border-zinc-300 px-2 py-1 text-zinc-800">
                            {i === 0 && "Subtotal: "}
                            {isNumeric ? formatCell(value, col.format) : `${value} linhas`}
                          </td>
                        );
                      })}
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
