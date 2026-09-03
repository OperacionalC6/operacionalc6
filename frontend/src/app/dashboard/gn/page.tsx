"use client";

/* eslint-disable react-hooks/set-state-in-effect --
 * Os dois efeitos desta página resetam loading/estado ao reagir a mudança de
 * área/ano/mês antes de rebuscar dado novo — o mesmo padrão do exemplo
 * oficial de "fetching data" do react.dev (setLoading(true) no início do
 * efeito). A regra é nova (vem por padrão no eslint-config-next do Next 16)
 * e mais rígida que essa recomendação oficial; suprimida aqui de propósito,
 * não por descuido.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, fetchGnAreaScorecard, fetchGnAreas, fetchMe } from "@/lib/api";
import { clearTokens, isLoggedIn } from "@/lib/auth";
import type { GnScorecardLoja, User } from "@/lib/types";

const MESES = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

function formatCurrency(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatPercent(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("pt-BR", { style: "percent", minimumFractionDigits: 1 });
}

function formatMesReferencia(iso: string | null): string {
  if (!iso) return "";
  const [ano, mes] = iso.split("-");
  return `${MESES[Number(mes) - 1]}/${ano}`;
}

export default function GnDashboardPage() {
  const router = useRouter();
  const hoje = new Date();

  const [user, setUser] = useState<User | null>(null);
  const [ano, setAno] = useState(hoje.getFullYear());
  const [mes, setMes] = useState(hoje.getMonth() + 1);
  const [areas, setAreas] = useState<string[]>([]);
  const [area, setArea] = useState<string>("");
  const [lojas, setLojas] = useState<GnScorecardLoja[]>([]);
  const [loadingAreas, setLoadingAreas] = useState(true);
  const [loadingScorecard, setLoadingScorecard] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Carrega o usuário logado e a lista de áreas disponíveis pro ano/mês escolhido.
  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/");
      return;
    }

    setLoadingAreas(true);
    setError(null);
    Promise.all([fetchMe(), fetchGnAreas(ano, mes)])
      .then(([meData, areasData]) => {
        setUser(meData);
        setAreas(areasData);
        setArea((current) => (areasData.includes(current) ? current : areasData[0] ?? ""));
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erro ao carregar áreas.");
      })
      .finally(() => setLoadingAreas(false));
  }, [ano, mes, router]);

  // Carrega o scorecard sempre que a área (ou período) selecionada mudar.
  useEffect(() => {
    if (!area) {
      setLojas([]);
      return;
    }
    setLoadingScorecard(true);
    setError(null);
    fetchGnAreaScorecard(area, ano, mes)
      .then((data) => setLojas(data.lojas))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erro ao carregar dados da área.");
        setLojas([]);
      })
      .finally(() => setLoadingScorecard(false));
  }, [area, ano, mes, router]);

  function handleLogout() {
    clearTokens();
    router.replace("/");
  }

  const lojasComContrato = lojas.filter((l) => l.qtd_contratos_mes > 0).length;
  const producaoTotal = lojas.reduce((sum, l) => sum + l.producao_mes, 0);
  const mesReferenciaMercado = lojas.find((l) => l.mercado_mes_referencia)?.mercado_mes_referencia ?? null;

  return (
    <div className="flex flex-1 flex-col bg-zinc-50">
      <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900">Comissão de GN — por área</h1>
          {user && (
            <p className="text-sm text-zinc-500">
              {user.full_name} · {user.role}
            </p>
          )}
        </div>
        <div className="flex items-center gap-4">
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

      <main className="flex-1 px-6 py-8">
        <div className="mb-6 flex flex-wrap items-end gap-4">
          <label className="flex flex-col text-sm text-zinc-600">
            Área
            <select
              value={area}
              onChange={(e) => setArea(e.target.value)}
              disabled={loadingAreas || areas.length === 0}
              className="mt-1 rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-zinc-900"
            >
              {areas.length === 0 && <option value="">Nenhuma área disponível</option>}
              {areas.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>

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
        </div>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        {!error && (loadingAreas || loadingScorecard) && (
          <p className="text-sm text-zinc-500">Carregando...</p>
        )}

        {!loadingAreas && !loadingScorecard && !error && (
          <>
            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-lg border border-zinc-200 bg-white p-6">
                <p className="text-sm text-zinc-500">Lojas na área</p>
                <p className="text-2xl font-semibold text-zinc-900">{lojas.length}</p>
              </div>
              <div className="rounded-lg border border-zinc-200 bg-white p-6">
                <p className="text-sm text-zinc-500">Com contrato no mês</p>
                <p className="text-2xl font-semibold text-zinc-900">{lojasComContrato}</p>
              </div>
              <div className="rounded-lg border border-zinc-200 bg-white p-6">
                <p className="text-sm text-zinc-500">Produção do mês</p>
                <p className="text-2xl font-semibold text-zinc-900">{formatCurrency(producaoTotal)}</p>
              </div>
            </div>

            <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-zinc-50 text-left text-zinc-500">
                    <tr>
                      <th className="px-4 py-2 font-medium">Loja</th>
                      <th className="px-4 py-2 text-right font-medium">Contratos (mês)</th>
                      <th className="px-4 py-2 text-right font-medium">Produção (mês)</th>
                      <th className="px-4 py-2 text-right font-medium">
                        Mercado potencial
                        <span className="block text-xs font-normal text-zinc-400">média 3 meses</span>
                      </th>
                      <th className="px-4 py-2 text-right font-medium">
                        Share
                        {mesReferenciaMercado && (
                          <span className="block text-xs font-normal text-zinc-400">
                            {formatMesReferencia(mesReferenciaMercado)}
                          </span>
                        )}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {lojas.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-4 py-6 text-center text-zinc-400">
                          Nenhuma loja encontrada pra essa área/período.
                        </td>
                      </tr>
                    )}
                    {lojas.map((loja) => (
                      <tr key={loja.cnpj_loja} className="border-t border-zinc-100">
                        <td className="px-4 py-2 text-zinc-700">
                          {loja.nome_loja ?? loja.cnpj_loja}
                          {loja.loja_nova && (
                            <span className="ml-2 rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-700">
                              nova
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-right text-zinc-700">{loja.qtd_contratos_mes}</td>
                        <td className="px-4 py-2 text-right text-zinc-700">
                          {formatCurrency(loja.producao_mes)}
                        </td>
                        <td className="px-4 py-2 text-right text-zinc-700">
                          {formatCurrency(loja.mercado_potencial_media_3m)}
                        </td>
                        <td className="px-4 py-2 text-right text-zinc-700">
                          {formatPercent(loja.share_mes_referencia)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
