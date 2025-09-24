'use client';

import { useEffect, useMemo, useState } from 'react';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { getStatsLicitacoesPorUf, StatsUF } from '@/services/api';

type PieDatum = { name: string; value: number };

const COLORS = ['#4f46e5', '#22c55e', '#f59e0b', '#ef4444', '#6b7280'];

export default function LicitacoesPorUfPie() {
  const [data, setData] = useState<StatsUF[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const result = await getStatsLicitacoesPorUf();
      setData(Array.isArray(result) ? result : []);
      setLoading(false);
    };
    fetchData();
  }, []);

  const pieData: PieDatum[] = useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) return [];
    const sorted = [...data].sort((a, b) => b.total - a.total);
    const top4 = sorted.slice(0, 4);
    const outrosTotal = sorted.slice(4).reduce((acc, cur) => acc + (cur.total || 0), 0);
    const transformed: PieDatum[] = top4.map((d) => ({ name: d.uf, value: d.total }));
    return outrosTotal > 0 ? [...transformed, { name: 'Outros', value: outrosTotal }] : transformed;
  }, [data]);

  if (loading) {
    return <div className="h-80 flex items-center justify-center">Carregando dados do gráfico...</div>;
  }

  if (pieData.length === 0) {
    return <div className="h-80 flex items-center justify-center">Não há dados para exibir.</div>;
  }

  const total = pieData.reduce((acc, d) => acc + d.value, 0) || 1;

  return (
    <div className="w-full h-80">
      <h3 className="font-semibold mb-4">Participação por UF (Top 4 + Outros)</h3>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart margin={{ top: 20, right: 120, bottom: 20, left: 20 }}>
          <Pie
            data={pieData}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={80}
            dataKey="value"
            nameKey="name"
            label={({ name, value }: { name?: string; value?: number }) => {
              const safeValue = typeof value === "number" ? value : 0;
              const percentage = total > 0 ? Math.round((safeValue / total) * 100) : 0;
              return `${name ?? "N/A"} (${percentage}%)`;
            }}
          >
            {pieData.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(v: number) => [v, 'Licitações']} />
          <Legend layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ right: 0 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

