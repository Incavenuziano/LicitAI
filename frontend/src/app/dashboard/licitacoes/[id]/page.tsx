'use client';

import { useState, useEffect, useMemo } from 'react';
import DOMPurify from 'dompurify';
import { getLicitacaoById } from '@/services/api';
import { Licitacao } from '@/types';
import Chatbot from '@/components/Chatbot';

export default function LicitacaoDetailPage({ params }: { params: { id: string } }) {
  const [licitacao, setLicitacao] = useState<Licitacao | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const licitacaoId = parseInt(params.id, 10);
    if (Number.isNaN(licitacaoId)) {
      setLoading(false);
      return;
    }

    const fetchData = async () => {
      setLoading(true);
      const data = await getLicitacaoById(licitacaoId);
      setLicitacao(data);
      setLoading(false);
    };

    fetchData();
  }, [params.id]);

  if (loading) {
    return <div className="p-6">Carregando detalhes da licitacao...</div>;
  }

  if (!licitacao) {
    return <div className="p-6">Licitacao nao encontrada.</div>;
  }

  const analise = licitacao.analises && licitacao.analises[0];
  const sanitizedAnalysis = useMemo(() => {
    if (!analise?.resultado) return '';
    return DOMPurify.sanitize(analise.resultado);
  }, [analise?.resultado]);

  const dataEncerramento = useMemo(() => {
    if (!licitacao.data_encerramento_proposta) return 'N/A';
    const dt = new Date(licitacao.data_encerramento_proposta);
    return Number.isNaN(dt.getTime()) ? 'N/A' : dt.toLocaleDateString('pt-BR');
  }, [licitacao.data_encerramento_proposta]);

  const valorEstimado = useMemo(() => {
    const raw = licitacao.valor_total_estimado;
    if (raw === null || raw === undefined) return 'N/A';
    if (typeof raw === 'string' && raw.trim() === '') return 'N/A';
    const num = Number(raw);
    return Number.isFinite(num)
      ? num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
      : 'N/A';
  }, [licitacao.valor_total_estimado]);

  const ufDisplay = licitacao.uf ?? 'N/A';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-800">{licitacao.objeto_compra}</h1>
        <p className="mt-2 text-lg text-gray-600">{licitacao.orgao_entidade_nome}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
        <div className="bg-white p-4 rounded-lg shadow-sm"><strong>UF:</strong> {ufDisplay}</div>
        <div className="bg-white p-4 rounded-lg shadow-sm"><strong>Encerramento:</strong> {dataEncerramento}</div>
        <div className="bg-white p-4 rounded-lg shadow-sm"><strong>Valor Estimado:</strong> {valorEstimado}</div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-4 rounded-lg shadow-sm">
          <h2 className="text-xl font-bold mb-2">Analise da IA</h2>
          {analise && sanitizedAnalysis ? (
            <div
              className="p-4 bg-gray-50 rounded border border-gray-200 overflow-auto max-h-[60vh] text-sm leading-relaxed"
              dangerouslySetInnerHTML={{ __html: sanitizedAnalysis }}
            />
          ) : (
            <p className="text-gray-500">Nenhuma analise disponivel para esta licitacao.</p>
          )}
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm">
          <h2 className="text-xl font-bold mb-2">Converse com o Edital</h2>
          <Chatbot licitacaoId={licitacao.id} />
        </div>
      </div>
    </div>
  );
}
