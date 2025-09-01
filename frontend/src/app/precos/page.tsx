'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useSession, signOut } from 'next-auth/react';
import { pesquisarPrecosPorItem, PesquisaPrecoResponse } from '@/services/api';

export default function PrecosIndexPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  
  const [descricao, setDescricao] = useState<string>('');
  const [fonte, setFonte] = useState<'comprasgov'|'pncp'|'ambas'>('comprasgov');
  const [resultados, setResultados] = useState<PesquisaPrecoResponse | null>(null);
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
    try {
      const res = await pesquisarPrecosPorItem(descricao, fonte);
      setResultados(res);
    } catch (e: any) {
      setError(e?.message || 'Falha ao realizar a pesquisa');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col">
      <div className="w-full max-w-5xl items-center justify-between font-mono text-sm flex mb-6">
        <h1 className="text-2xl font-bold">Pesquisa de Mercado de Preços</h1>
      </div>

      <div className="w-full max-w-5xl space-y-3">
        <p className="text-gray-600">Pesquise o preço de um item ou serviço em diversas fontes públicas.</p>
        <div className="flex items-center gap-2">
          <input
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            type="text"
            placeholder="Ex: cadeira de escritório, serviço de limpeza"
            className="border rounded px-3 py-2 w-full md:w-96"
          />
          <select value={fonte} onChange={(e) => setFonte(e.target.value as any)} className="border rounded px-2 py-2">
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
                <div><span className="text-gray-500">Preços Encontrados:</span> {resultados.precos_encontrados}</div>
                <div><span className="text-gray-500">Mín:</span> {resultados.stats.min?.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'}) ?? '—'}</div>
                <div><span className="text-gray-500">Mediana:</span> {resultados.stats.median?.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'}) ?? '—'}</div>
                <div><span className="text-gray-500">Máx:</span> {resultados.stats.max?.toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'}) ?? '—'}</div>
                </div>
            </div>

            {resultados.detalhes.length > 0 && (
                 <div className="rounded border p-4 bg-white">
                 <h2 className="font-semibold mb-2">Detalhes dos Preços Encontrados (amostra)</h2>
                 <div className="max-h-96 overflow-auto">
                    <table className="w-full text-sm">
                    <thead>
                        <tr className="text-left border-b">
                        <th className="py-2">ID da Referência (Contrato/Licitação)</th>
                        <th className="py-2">Preço</th>
                        </tr>
                    </thead>
                    <tbody>
                        {resultados.detalhes.map((d, i) => (
                        <tr key={i} className="border-b hover:bg-gray-50">
                            <td className="py-2">{d.referencia_id}</td>
                            <td className="py-2">{d.preco.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</td>
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
