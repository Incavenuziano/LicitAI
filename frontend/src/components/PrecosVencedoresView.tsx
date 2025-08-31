"use client";

import { useEffect, useState } from "react";
import { getPrecosVencedores, PrecoVencedorResponse } from "@/services/api";

export default function PrecosVencedoresView({ licitacaoId, defaultFonte = 'comprasgov' as 'comprasgov'|'pncp'|'ambas' }) {
  const [fonte, setFonte] = useState<'comprasgov'|'pncp'|'ambas'>(defaultFonte);
  const [data, setData] = useState<PrecoVencedorResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getPrecosVencedores(licitacaoId, fonte, 20);
      setData(res);
    } catch (e: any) {
      setError(e?.message || 'Falha ao carregar preços');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!Number.isFinite(licitacaoId)) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [licitacaoId, fonte]);

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3 mb-2">
        <label className="text-sm text-gray-600">Fonte:</label>
        <select
          value={fonte}
          onChange={(e) => setFonte(e.target.value as any)}
          className="border rounded px-2 py-1 text-sm"
        >
          <option value="comprasgov">ComprasGov (Contratos)</option>
          <option value="pncp">PNCP (heurístico)</option>
          <option value="ambas">Ambas</option>
        </select>
        <button onClick={load} className="text-sm bg-indigo-600 hover:bg-indigo-700 text-white py-1 px-3 rounded">
          Recarregar
        </button>
      </div>

      {loading && <div className="text-gray-500">Carregando...</div>}
      {error && <div className="text-red-600">{error}</div>}

      {data && !loading && (
        <div className="space-y-4">
          <div className="rounded border p-4 bg-white">
            <h2 className="font-semibold mb-2">Licitação base</h2>
            <div className="text-sm text-gray-700">
              <div><span className="font-medium">ID:</span> {data.base.id}</div>
              <div><span className="font-medium">Número PNCP:</span> {data.base.numero_controle_pncp || 'N/A'}</div>
              <div><span className="font-medium">Objeto:</span> {data.base.objeto_compra || 'N/A'}</div>
            </div>
          </div>

          <div className="rounded border p-4 bg-white">
            <h2 className="font-semibold mb-2">Estatísticas</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
              <div><span className="text-gray-500">Similares:</span> {data.similares_considerados}</div>
              <div><span className="text-gray-500">Preços:</span> {data.precos_encontrados}</div>
              <div><span className="text-gray-500">Mín:</span> {data.stats.min ?? '—'}</div>
              <div><span className="text-gray-500">Mediana:</span> {data.stats.median ?? '—'}</div>
              <div><span className="text-gray-500">Máx:</span> {data.stats.max ?? '—'}</div>
            </div>
          </div>

          <div className="rounded border p-4 bg-white">
            <h2 className="font-semibold mb-2">Detalhes (amostra)</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b">
                  <th className="py-2">Licitação ID</th>
                  <th className="py-2">Preço</th>
                </tr>
              </thead>
              <tbody>
                {data.detalhes.slice(0, 30).map((d, i) => (
                  <tr key={i} className="border-b hover:bg-gray-50">
                    <td className="py-2">{d.licitacao_id}</td>
                    <td className="py-2">{d.preco.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</td>
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

