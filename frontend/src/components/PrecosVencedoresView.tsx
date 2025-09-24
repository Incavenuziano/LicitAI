'use client';

import { useEffect, useState } from 'react';
import { getPrecosVencedores } from '@/services/api';
import { PrecoVencedorResponse } from '@/types';

type FontePreco = 'comprasgov' | 'pncp' | 'ambas';

interface Props {
  licitacaoId: number;
  defaultFonte?: FontePreco;
}

const fonteOptions: FontePreco[] = ['comprasgov', 'pncp', 'ambas'];
const fonteLabels: Record<FontePreco, string> = {
  comprasgov: 'ComprasGov (Contratos)',
  pncp: 'PNCP (heuristico)',
  ambas: 'Ambas',
};

const formatCurrency = (value: number | null | undefined): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'N/A';
  }
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
};

export default function PrecosVencedoresView({ licitacaoId, defaultFonte = 'comprasgov' }: Props) {
  const [fonte, setFonte] = useState<FontePreco>(defaultFonte);
  const [data, setData] = useState<PrecoVencedorResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getPrecosVencedores(licitacaoId, fonte, 20);
      setData(response);
    } catch (err: any) {
      setError(err?.message || 'Falha ao carregar precos');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!Number.isFinite(licitacaoId)) {
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [licitacaoId, fonte]);

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3 mb-2">
        <label className="text-sm text-gray-600">Fonte:</label>
        <select
          value={fonte}
          onChange={(event) => setFonte(event.target.value as FontePreco)}
          className="border rounded px-2 py-1 text-sm"
        >
          {fonteOptions.map((option) => (
            <option key={option} value={option}>
              {fonteLabels[option]}
            </option>
          ))}
        </select>
        <button
          onClick={load}
          className="text-sm bg-indigo-600 hover:bg-indigo-700 text-white py-1 px-3 rounded"
        >
          Recarregar
        </button>
      </div>

      {loading && <div className="text-gray-500">Carregando...</div>}
      {error && <div className="text-red-600">{error}</div>}

      {data && !loading && (
        <div className="space-y-4">
          <div className="rounded border p-4 bg-white">
            <h2 className="font-semibold mb-2">Licitacao base</h2>
            <div className="text-sm text-gray-700 space-y-1">
              <div>
                <span className="font-medium">ID:</span> {data.base.id}
              </div>
              <div>
                <span className="font-medium">Numero PNCP:</span> {data.base.numero_controle_pncp || 'N/A'}
              </div>
              <div>
                <span className="font-medium">Objeto:</span> {data.base.objeto_compra || 'N/A'}
              </div>
            </div>
          </div>

          <div className="rounded border p-4 bg-white">
            <h2 className="font-semibold mb-2">Estatisticas</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
              <div><span className="text-gray-500">Similares:</span> {data.similares_considerados}</div>
              <div><span className="text-gray-500">Precos:</span> {data.precos_encontrados}</div>
              <div><span className="text-gray-500">Min:</span> {formatCurrency(data.stats.min)}</div>
              <div><span className="text-gray-500">Mediana:</span> {formatCurrency(data.stats.median)}</div>
              <div><span className="text-gray-500">Max:</span> {formatCurrency(data.stats.max)}</div>
            </div>
          </div>

          <div className="rounded border p-4 bg-white">
            <h2 className="font-semibold mb-2">Detalhes (amostra)</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2">Licitacao ID</th>
                  <th className="py-2">Preco</th>
                </tr>
              </thead>
              <tbody>
                {data.detalhes.slice(0, 30).map((item, index) => (
                  <tr key={`${item.licitacao_id}-${index}`} className="border-b hover:bg-gray-50">
                    <td className="py-2">{item.licitacao_id}</td>
                    <td className="py-2">{formatCurrency(item.preco)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
