'use client';

import { useEffect, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { getStatsLicitacoesPorUf, StatsUF } from '@/services/api';

export default function LicitacoesPorUfChart() {
  const [data, setData] = useState<StatsUF[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const result = await getStatsLicitacoesPorUf();
      // Pega apenas os 15 estados com mais licitações para um gráfico mais limpo
      setData(result.slice(0, 15));
      setLoading(false);
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="h-80 flex items-center justify-center">
        Carregando dados do gráfico...
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="h-80 flex items-center justify-center">
        Não há dados para exibir.
      </div>
    );
  }

  return (
    <div className="w-full h-80">
      <h3 className="font-semibold mb-4">Licitações por Estado (Top 15)</h3>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 50, right: 20, left: 20, bottom: 24 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="uf" />
          <YAxis />
          <Tooltip />
          <Legend verticalAlign="top" align="right" height={36} wrapperStyle={{ top: 0, right: 0 }} />
          <Bar dataKey="total" fill="#4f46e5" name="Total de Licitações" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

