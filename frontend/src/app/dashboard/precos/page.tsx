'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useSession } from 'next-auth/react';
import {
  pesquisarPrecosPorItem,
  PesquisaPrecoResponse,
  getSeriePrecos,
  SeriePrecosResponse,
} from '@/services/api';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

export default function PrecosIndexPage() {
  const { status } = useSession();
  const router = useRouter();

  const [descricao, setDescricao] = useState<string>('');
  const [fonte, setFonte] = useState<'comprasgov' | 'pncp' | 'ambas'>('comprasgov');
  const [resultados, setResultados] = useState<PesquisaPrecoResponse | null>(null);
  const [serie, setSerie] = useState<SeriePrecosResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (status === 'unauthenticated') {
    router.push('/login');
    return null;
  }

  const handleSearch = async () => {
    if (!descricao.trim()) return;
    setLoading(true);
    setError(null);
    setResultados(null);
    setSerie(null);
    try {
      const res = await pesquisarPrecosPorItem(descricao, fonte);
      setResultados(res);
    } catch (e: any) {
      setError(e?.message || 'Falha ao realizar a pesquisa');
    } finally {
      setLoading(false);
    }
  };

  // Serie por CNPJ (Portal da Transparencia)
  const [cnpj, setCnpj] = useState<string>('');
  const [dataInicio, setDataInicio] = useState<string>('');
  const [dataFim, setDataFim] = useState<string>('');
  const [loadingSerie, setLoadingSerie] = useState(false);

  const handleSerie = async () => {
    if (!cnpj.trim()) return;
    setLoadingSerie(true);
    setError(null);
    setSerie(null);
    try {
      const res = await getSeriePrecos({
        cnpj,
        fonte: 'transparencia',
        data_inicio: dataInicio || undefined,
        data_fim: dataFim || undefined,
      });
      setSerie(res);
    } catch (e: any) {
      setError(e?.message || 'Falha ao obter serie de precos');
    } finally {
      setLoadingSerie(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col">
      <div className="w-full max-w-5xl items-center justify-between font-mono text-sm flex mb-6">
        <h1 className="text-2xl font-bold">Pesquisa de Mercado de Precos</h1>
      </div>

      <div className="w-full max-w-5xl space-y-3 mt-6">
        <div className="p-4 border rounded bg-white">
          <h2 className="font-semibold mb-2">Serie Historica por CNPJ (Portal da Transparencia)</h2>
          <div className="flex flex-wrap items-end gap-2">
            <div>
              <label className="block text-xs text-gray-600">CNPJ</label>
              <input
                value={cnpj}
                onChange={(e) => setCnpj(e.target.value)}
                placeholder="00.000.000/0000-00 ou somente digitos"
                className="border rounded px-3 py-2 w-64"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600">Data inicio</label>
              <input
                type="date"
                value={dataInicio}
                onChange={(e) => setDataInicio(e.target.value)}
                className="border rounded px-3 py-2"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600">Data fim</label>
              <input
                type="date"
                value={dataFim}
                onChange={(e) => setDataFim(e.target.value)}
                className="border rounded px-3 py-2"
              />
            </div>
            <button
              onClick={handleSerie}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-4 py-2 rounded disabled:bg-gray-400"
              disabled={!cnpj || loadingSerie}
            >
              {loadingSerie ? 'Carregando...' : 'Ver serie'}
            </button>
          </div>
          {serie && (
            <div className="mt-4">
              <div className="text-sm text-gray-600 mb-2">
                Pontos: {serie.series.length} | Media:{' '}
                {serie.stats.mean?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) ?? '-'}
              </div>
              <div style={{ width: '100%', height: 320 }}>
                <ResponsiveContainer>
                  <LineChart data={serie.series} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis
                      tickFormatter={(value: number) =>
                        value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
                      }
                      width={90}
                    />
                    <Tooltip
                      formatter={(value: any) =>
                        Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
                      }
                      labelFormatter={(label) => `Data: ${label}`}
                    />
                    <Line type="monotone" dataKey="value" stroke="#2563eb" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="w-full max-w-5xl space-y-3">
        <p className="text-gray-600">Pesquise o preco de um item ou servico em diversas fontes publicas.</p>
        <div className="flex items-center gap-2">
          <input
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            type="text"
            placeholder="Ex: cadeira de escritorio, servico de limpeza"
            className="border rounded px-3 py-2 w-full md:w-96"
          />
          <select
            value={fonte}
            onChange={(e) => setFonte(e.target.value as 'comprasgov' | 'pncp' | 'ambas')}
            className="border rounded px-2 py-2"
          >
            <option value="comprasgov">ComprasGov</option>
            <option value="pncp">PNCP</option>
            <option value="ambas">Ambas</option>
          </select>
          <button
            onClick={handleSearch}
            className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-4 py-2 rounded disabled:bg-gray-400"
            disabled={!descricao || loading}
          >
            {loading ? 'Pesquisando...' : 'Pesquisar'}
          </button>
        </div>
      </div>

      {error && <div className="mt-4 text-red-500 p-4 bg-red-50 rounded-md">{error}</div>}

      {resultados && (
        <div className="mt-6 w-full max-w-5xl space-y-4">
          <div className="rounded border p-4 bg-white">
            <h2 className="font-semibold mb-2">Resultados para "{resultados.query}"</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div>
                <span className="text-gray-500">Precos Encontrados:</span> {resultados.precos_encontrados}
              </div>
              <div>
                <span className="text-gray-500">Min:</span>{' '}
                {resultados.stats.min?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) ?? 'N/A'}
              </div>
              <div>
                <span className="text-gray-500">Mediana:</span>{' '}
                {resultados.stats.median?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) ?? 'N/A'}
              </div>
              <div>
                <span className="text-gray-500">Max:</span>{' '}
                {resultados.stats.max?.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) ?? 'N/A'}
              </div>
            </div>
          </div>

          {resultados.detalhes.length > 0 && (
            <div className="rounded border p-4 bg-white">
              <h2 className="font-semibold mb-2">Detalhes dos Precos Encontrados (amostra)</h2>
              <div className="max-h-96 overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left border-b">
                      <th className="py-2">ID da Referencia (Contrato ou Licitacao)</th>
                      <th className="py-2">Preco</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultados.detalhes.map((item, index) => (
                      <tr key={index} className="border-b hover:bg-gray-50">
                        <td className="py-2">{item.referencia_id}</td>
                        <td className="py-2">
                          {item.preco.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
