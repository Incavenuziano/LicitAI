"use client"; // Indica que este é um Componente de Cliente

import { useEffect, useState } from 'react';
import { getLicitacoes } from '@/services/api';
import { Licitacao } from '@/types';

export default function LicitacoesTabela() {
  // 'useState' para armazenar a lista de licitações
  const [licitacoes, setLicitacoes] = useState<Licitacao[]>([]);
  // 'useState' para controlar o estado de carregamento
  const [loading, setLoading] = useState(true);

  // 'useEffect' para buscar os dados da API quando o componente for montado
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const data = await getLicitacoes();
      setLicitacoes(data);
      setLoading(false);
    };

    fetchData();
  }, []); // O array vazio [] garante que isso rode apenas uma vez

  // Se estiver carregando, exibe uma mensagem
  if (loading) {
    return <p>Carregando licitações...</p>;
  }

  // Renderiza a tabela com os dados
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Licitações Encontradas</h1>
      <div className="overflow-x-auto">
        <table className="min-w-full bg-white border border-gray-200">
          <thead>
            <tr className="bg-gray-100">
              <th className="py-2 px-4 border-b">Órgão</th>
              <th className="py-2 px-4 border-b">Objeto</th>
              <th className="py-2 px-4 border-b">Data de Encerramento</th>
              <th className="py-2 px-4 border-b">Valor Estimado</th>
            </tr>
          </thead>
          <tbody>
            {licitacoes.map((licitacao) => (
              <tr key={licitacao.id} className="hover:bg-gray-50">
                <td className="py-2 px-4 border-b">{licitacao.orgao_entidade_nome}</td>
                <td className="py-2 px-4 border-b">{licitacao.objeto_compra}</td>
                <td className="py-2 px-4 border-b">
                  {licitacao.data_encerramento_proposta 
                    ? new Date(licitacao.data_encerramento_proposta).toLocaleDateString('pt-BR') 
                    : 'N/A'}
                </td>
                <td className="py-2 px-4 border-b text-right">
                  {licitacao.valor_total_estimado 
                    ? parseFloat(licitacao.valor_total_estimado).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' }) 
                    : 'N/A'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
