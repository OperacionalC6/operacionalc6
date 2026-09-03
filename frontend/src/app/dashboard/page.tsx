"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, fetchMe, fetchMetrics } from "@/lib/api";
import { clearTokens, isLoggedIn } from "@/lib/auth";
import type { Metric, User } from "@/lib/types";

function formatCurrency(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/");
      return;
    }

    const dateTo = new Date();
    const dateFrom = new Date();
    dateFrom.setDate(dateFrom.getDate() - 90);
    const toIsoDate = (d: Date) => d.toISOString().slice(0, 10);

    Promise.all([
      fetchMe(),
      fetchMetrics({ date_from: toIsoDate(dateFrom), date_to: toIsoDate(dateTo) }),
    ])
      .then(([meData, metricsData]) => {
        setUser(meData);
        setMetrics(metricsData);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/");
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erro ao carregar dados.");
      })
      .finally(() => setLoading(false));
  }, [router]);

  function handleLogout() {
    clearTokens();
    router.replace("/");
  }

  const total = metrics.reduce((sum, m) => sum + Number(m.value), 0);

  return (
    <div className="flex flex-1 flex-col bg-zinc-50">
      <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900">Operacional C6</h1>
          {user && (
            <p className="text-sm text-zinc-500">
              {user.full_name} · {user.role}
            </p>
          )}
        </div>
        <div className="flex items-center gap-4">
          <Link href="/dashboard/gn" className="text-sm text-zinc-600 hover:text-zinc-900">
            Comissão de GN →
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
        {loading && <p className="text-sm text-zinc-500">Carregando...</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}

        {!loading && !error && (
          <>
            <div className="mb-6 rounded-lg border border-zinc-200 bg-white p-6">
              <p className="text-sm text-zinc-500">Total (últimos 90 dias)</p>
              <p className="text-2xl font-semibold text-zinc-900">{formatCurrency(total)}</p>
            </div>

            <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white">
              <table className="w-full text-sm">
                <thead className="bg-zinc-50 text-left text-zinc-500">
                  <tr>
                    <th className="px-4 py-2 font-medium">Data</th>
                    <th className="px-4 py-2 font-medium">Métrica</th>
                    <th className="px-4 py-2 font-medium">Fonte</th>
                    <th className="px-4 py-2 text-right font-medium">Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {metrics.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-zinc-400">
                        Nenhum registro encontrado no período.
                      </td>
                    </tr>
                  )}
                  {metrics.map((m) => (
                    <tr key={m.id} className="border-t border-zinc-100">
                      <td className="px-4 py-2 text-zinc-700">{m.metric_date}</td>
                      <td className="px-4 py-2 text-zinc-700">{m.metric_name}</td>
                      <td className="px-4 py-2 text-zinc-500">{m.source}</td>
                      <td className="px-4 py-2 text-right text-zinc-700">
                        {formatCurrency(Number(m.value))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
