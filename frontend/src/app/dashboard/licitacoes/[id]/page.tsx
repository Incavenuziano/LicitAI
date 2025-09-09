'use client';

import { useState, useEffect } from 'react';
import { getLicitacaoById } from '@/services/api';
import { Licitacao } from '@/types';
import Chatbot from '@/components/Chatbot';

export default function LicitacaoDetailPage({ params }: { params: { id: string } }) {
  const [licitacao, setLicitacao] = useState<Licitacao | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const licitacaoId = parseInt(params.id, 10);
    if (isNaN(licitacaoId)) {
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
    return <div className="p-6">Carregando detalhes da licitação...</div>;
  }

  if (!licitacao) {
    return <div className="p-6">Licitação não encontrada.</div>;
  }

  const analise = licitacao.analises && licitacao.analises[0];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-800">{licitacao.objeto_compra}</h1>
        <p className="mt-2 text-lg text-gray-600">{licitacao.orgao_entidade_nome}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
        <div className="bg-white p-4 rounded-lg shadow-sm"><strong>UF:</strong> {licitacao.uf}</div>
        <div className="bg-white p-4 rounded-lg shadow-sm"><strong>Encerramento:</strong> {new Date(licitacao.data_encerramento_proposta!).toLocaleDateString('pt-BR')}</div>
        <div className="bg-white p-4 rounded-lg shadow-sm"><strong>Valor Estimado:</strong> {parseFloat(licitacao.valor_total_estimado!).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'})}</div>
      </div>

      {/* Seção de Análise e Chatbot */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-4 rounded-lg shadow-sm">
          <h2 className="text-xl font-bold mb-2">Análise da IA</h2>
          {analise ? (
            <div className="whitespace-pre-wrap font-mono text-xs p-4 bg-gray-50 rounded overflow-auto max-h-[60vh]">
              {analise.resultado}
            </div>
          ) : (
            <p className="text-gray-500">Nenhuma análise disponível para esta licitação.</p>
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
