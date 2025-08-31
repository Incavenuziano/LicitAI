"use client";

import { useEffect, useMemo, useState } from "react";
import { getDashboardSummary } from "@/services/dashboard";
import type { DashboardSummary } from "@/types";

const COLORS = ["#2563eb", "#16a34a", "#f59e0b", "#ef4444", "#14b8a6", "#a855f7"];

export default function Dashboard() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const d = await getDashboardSummary();
        setData(d);
      } catch (e: any) {
        setError(e?.message || "Falha ao carregar dashboard");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const ufTop = useMemo(() => {
    if (!data) return [] as { uf: string; count: number }[];
    return [...data.by_uf].sort((a, b) => b.count - a.count).slice(0, 12);
  }, [data]);

  // Defina todos os hooks antes de qualquer return condicional
  const byTipoSafe = (data?.by_tipo ?? []) as { tipo: string; count: number }[];
  const pieStyle = useMemo(() => {
    const total = byTipoSafe.reduce((s, x) => s + (x.count || 0), 0) || 1;
    const colors = ["#2563eb", "#16a34a", "#f59e0b"];
    let acc = 0;
    const parts = byTipoSafe.map((x, i) => {
      const start = (acc / total) * 360;
      acc += x.count;
      const end = (acc / total) * 360;
      return `${colors[i % colors.length]} ${start}deg ${end}deg`;
    });
    return {
      backgroundImage: `conic-gradient(${parts.join(", ")})`,
    } as React.CSSProperties;
  }, [byTipoSafe]);

  if (loading) return <div className="w-full mb-6 text-gray-600">Carregando dashboard...</div>;
  if (error) return <div className="w-full mb-6 text-red-600">{error}</div>;
  if (!data) return null;

  const { kpis, by_tipo } = data;

  return (
    <section className="w-full mb-8">
      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <KpiCard title="Novas licitações hoje" value={kpis.novas_hoje.toLocaleString("pt-BR")} />
        <KpiCard
          title="Valor total em aberto"
          value={kpis.valor_total_aberto.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })}
        />
        <KpiCard title="Análises concluídas" value={kpis.analises_concluidas.toLocaleString("pt-BR")} />
      </div>

      {/* Gráficos (fallback sem libs) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded border bg-white p-4">
          <h3 className="font-semibold mb-2">Distribuição por tipo</h3>
          <div className="flex items-center gap-6">
            <div className="w-48 h-48 rounded-full" style={pieStyle} />
            <div className="space-y-2 text-sm">
              {by_tipo.map((x, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                  <span className="text-gray-700">{x.tipo}</span>
                  <span className="text-gray-500">({x.count})</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="rounded border bg-white p-4">
          <h3 className="font-semibold mb-2">UFs com mais licitações</h3>
          <div className="space-y-2">
            {ufTop.map((u) => {
              const max = ufTop[0]?.count || 1;
              const w = Math.max(4, Math.round((u.count / max) * 100));
              return (
                <div key={u.uf} className="text-sm">
                  <div className="flex justify-between mb-1"><span>{u.uf}</span><span className="text-gray-500">{u.count}</span></div>
                  <div className="h-2 bg-gray-200 rounded">
                    <div className="h-2 bg-indigo-600 rounded" style={{ width: `${w}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

function KpiCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded border bg-white p-4">
      <div className="text-sm text-gray-500">{title}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
    </div>
  );
}
