'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useSession, signOut } from 'next-auth/react';
import { getLicitacoes, ragIndexar, ragPerguntar } from '@/services/api';
import { requestAnalises } from '@/services/api';
import type { Licitacao } from '@/types';
import PrecosVencedoresView from '@/components/PrecosVencedoresView';

export default function LicitacaoDossiePage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const licitacaoId = Number(params.id);

  const [licitacao, setLicitacao] = useState<Licitacao | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  // RAG state
  const [ragQuestion, setRagQuestion] = useState('');
  const [ragLoading, setRagLoading] = useState(false);
  const [ragIndexing, setRagIndexing] = useState(false);
  const [ragAnswers, setRagAnswers] = useState<{ q: string; a: string }[]>([]);
  const [isRequesting, setIsRequesting] = useState(false);

  useEffect(() => {
    if (status === 'unauthenticated') {
      router.push('/login');
    }
  }, [status, router]);

  const fetchLicitacao = async () => {
    try {
      setLoading(true);
      const all = await getLicitacoes();
      const l = all.find((x) => x.id === licitacaoId) || null;
      if (!l) throw new Error('Licitação não encontrada');
      setLicitacao(l);
    } catch (e: any) {
      setErr(e?.message || 'Falha ao carregar licitação');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (Number.isFinite(licitacaoId)) fetchLicitacao();
  }, [licitacaoId]);

  const handleSolicitarAnalise = async () => {
    if (!Number.isFinite(licitacaoId)) return;
    setIsRequesting(true);
    try {
      await requestAnalises([licitacaoId]);
      await fetchLicitacao();
      alert('Análise solicitada com sucesso.');
    } catch (e: any) {
      alert(e?.message || 'Falha ao solicitar análise');
    } finally {
      setIsRequesting(false);
    }
  };

  const analise = useMemo(() => (licitacao?.analises && licitacao.analises[0]) || null, [licitacao]);

  const handleRagAsk = async () => {
    if (!licitacao?.id || !ragQuestion.trim()) return;
    setRagLoading(true);
    try {
      const r = await ragPerguntar(licitacao.id, ragQuestion, 4);
      const answer = (r.results && r.results.length > 0)
        ? r.results.map((x) => x.chunk).join('\n\n---\n\n')
        : 'Nenhum trecho encontrado. Dica: clique em "Indexar" antes e tente novamente.';
      setRagAnswers((prev) => [{ q: ragQuestion, a: answer }, ...prev]);
      setRagQuestion('');
    } catch (e: any) {
      alert(e?.message || 'Falha ao consultar o edital');
    } finally {
      setRagLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col">
      <div className="w-full max-w-5xl items-center justify-between font-mono text-sm flex mb-6">
        <h1 className="text-2xl font-bold">Dossiê da Licitação</h1>
        {status === 'authenticated' && session?.user && (
          <button onClick={() => signOut()} className="ml-4 bg-red-500 hover:bg-red-700 text-white font-bold py-2 px-4 rounded">
            Sair
          </button>
        )}
      </div>

      {loading && <div className="text-gray-600">Carregando...</div>}
      {err && <div className="text-red-600">{err}</div>}

      {!loading && licitacao && (
        <div className="space-y-6">
          {/* Cabeçalho */}
          <section className="rounded border p-4 bg-white">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-sm text-gray-500">ID: {licitacao.id}</div>
                <h2 className="text-xl font-semibold mt-1">{licitacao.orgao_entidade_nome || 'Órgão'}</h2>
                <div className="text-gray-700 mt-1 max-w-3xl">{licitacao.objeto_compra || '—'}</div>
              </div>
              {licitacao.link_sistema_origem && (
                <Link href={licitacao.link_sistema_origem} target="_blank" className="text-sm text-indigo-600 hover:underline">
                  Acessar Edital
                </Link>
              )}
            </div>
            <div className="text-sm text-gray-600 mt-3 grid grid-cols-2 md:grid-cols-4 gap-2">
              <div><span className="text-gray-500">UF:</span> {licitacao.uf || '—'}</div>
              <div><span className="text-gray-500">Município:</span> {licitacao.municipio_nome || '—'}</div>
              <div><span className="text-gray-500">Encerramento:</span> {licitacao.data_encerramento_proposta ? new Date(licitacao.data_encerramento_proposta).toLocaleDateString('pt-BR') : '—'}</div>
              <div><span className="text-gray-500">Valor estimado:</span> {licitacao.valor_total_estimado ? parseFloat(licitacao.valor_total_estimado).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) : '—'}</div>
            </div>
          </section>

          {/* Análise do edital + RAG */}
          <section className="rounded border p-4 bg-white">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold">Análise do Edital</h3>
              <div className="flex items-center gap-2">
                {analise?.status && (
                  <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-700">{analise.status}</span>
                )}
                <button
                  onClick={handleSolicitarAnalise}
                  disabled={isRequesting || ['pendente','processando','em andamento'].includes(String(analise?.status || '').toLowerCase())}
                  className="px-3 py-1 text-sm bg-purple-600 text-white rounded disabled:bg-gray-400"
                >
                  {isRequesting ? 'Solicitando...' : 'Solicitar Análise'}
                </button>
              </div>
            </div>
            {analise?.resultado ? (
              <div className="whitespace-pre-wrap bg-gray-50 p-3 rounded border text-sm max-h-96 overflow-auto">
                {analise.resultado}
              </div>
            ) : (
              <div className="text-sm text-gray-500">Sem resultado de análise disponível.</div>
            )}

            <div className="mt-3">
              <h4 className="font-semibold mb-2 text-sm">Perguntar ao Edital (RAG)</h4>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={ragQuestion}
                  onChange={(e) => setRagQuestion(e.target.value)}
                  placeholder="Ex.: Data limite para entrega? Garantia exigida?"
                  className="flex-1 px-3 py-2 border rounded"
                />
                <button
                  onClick={async () => {
                    if (!licitacao?.id) return;
                    setRagIndexing(true);
                    try { await ragIndexar(licitacao.id); } catch (e: any) { alert(e?.message || 'Falha ao indexar'); }
                    finally { setRagIndexing(false); }
                  }}
                  className="px-3 py-2 bg-gray-200 rounded hover:bg-gray-300"
                  disabled={ragIndexing}
                >
                  {ragIndexing ? 'Indexando...' : 'Indexar'}
                </button>
                <button
                  onClick={handleRagAsk}
                  disabled={ragLoading || !ragQuestion.trim()}
                  className="px-3 py-2 bg-indigo-600 text-white rounded disabled:bg-gray-400"
                >
                  {ragLoading ? 'Perguntando...' : 'Perguntar'}
                </button>
              </div>
              {ragAnswers.length > 0 && (
                <div className="space-y-3 max-h-64 overflow-auto">
                  {ragAnswers.map((m, idx) => (
                    <div key={idx} className="text-sm">
                      <div className="text-gray-600">Q: {m.q}</div>
                      <div className="whitespace-pre-wrap mt-1 border rounded p-2 bg-gray-50">
                        {m.a}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* Preços vencedores (embed) */}
          <section className="rounded border p-4 bg-white">
            <h3 className="font-semibold mb-3">Preços vencedores (similares)</h3>
            <PrecosVencedoresView licitacaoId={licitacao.id} defaultFonte="comprasgov" />
          </section>
        </div>
      )}
    </main>
  );
}
