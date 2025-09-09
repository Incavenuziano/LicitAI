'use client';

import { useEffect, useMemo, useState } from "react";
import { getLicitacoes } from "@/services/api";
import { Licitacao, Analise } from "@/types";

// Componente reutilizado para mostrar o status e o botão
const StatusAnalise: React.FC<{ 
  analise: Analise;
  onVerResultado: () => void;
}> = ({ analise, onVerResultado }) => {
  const getStatusStyle = (status: string) => {
    switch (status) {
      case "Concluído":
      case "Concluido":
        return "bg-green-100 text-green-800";
      case "Erro":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };
  return (
    <div className="flex flex-col items-center gap-1">
      <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusStyle(analise.status)}`}>
        {analise.status}
      </span>
      <button onClick={onVerResultado} className="text-xs text-blue-600 hover:underline">
        Ver Resultado
      </button>
    </div>
  );
};

export default function AnalisesTabela() {
  const [todasLicitacoes, setTodasLicitacoes] = useState<Licitacao[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAnalise, setSelectedAnalise] = useState<{ resultado: string; orgao?: string | null; numero?: string | null; } | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const data = await getLicitacoes(); // Busca todas as licitações
      setTodasLicitacoes(data);
      setLoading(false);
    };
    fetchData();
  }, []);

  const analisesConcluidas = useMemo(() => {
    return todasLicitacoes
      .map(l => 
        l.analises?.filter(a => a.status === 'Concluido' || a.status === 'Concluído' || a.status === 'Erro').map(a => ({ ...l, analise: a }))
      )
      .flat()
      .filter((item): item is Licitacao & { analise: Analise } => !!item);
  }, [todasLicitacoes]);

  const handleShowResultado = (licitacao: Licitacao & { analise: Analise }) => {
    setSelectedAnalise({
      resultado: licitacao.analise.resultado,
      orgao: licitacao.orgao_entidade_nome,
      numero: licitacao.numero_controle_pncp,
    });
  };

  if (loading) return <p>Carregando análises...</p>;

  return (
    <div className="container mx-auto">
      {/* Modal de Resultado da Análise */}
      {selectedAnalise && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
          <div className="bg-white p-6 rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-bold">
                Resultado da Análise · {selectedAnalise.orgao} · {selectedAnalise.numero}
              </h3>
              <button onClick={() => setSelectedAnalise(null)} className="text-gray-500 hover:text-gray-800 text-2xl">&times;</button>
            </div>
            <div className="whitespace-pre-wrap bg-gray-50 p-4 rounded border font-mono text-sm overflow-auto">
              {selectedAnalise.resultado}
            </div>
          </div>
        </div>
      )}

      {/* Tabela de Análises */}
      <div className="rounded-lg border bg-white shadow-sm">
        <div className="max-h-[75vh] overflow-y-auto">
          {analisesConcluidas.length > 0 ? (
            <table className="min-w-full w-full text-sm">
              <thead className="sticky top-0 bg-gray-50 z-10">
                <tr>
                  <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-gray-700">Órgão</th>
                  <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-gray-700">Objeto da Licitação</th>
                  <th className="py-3 px-4 border-b border-gray-200 text-left font-semibold text-gray-700 whitespace-nowrap">Data da Análise</th>
                  <th className="py-3 px-4 border-b border-gray-200 text-center font-semibold text-gray-700">Status</th>
                </tr>
              </thead>
              <tbody>
                {analisesConcluidas.map((item) => (
                  <tr key={`${item.id}-${item.analise.id}`} className="odd:bg-gray-50 hover:bg-gray-100">
                    <td className="py-2 px-4 border-b">{item.orgao_entidade_nome}</td>
                    <td className="py-2 px-4 border-b">
                      <div className="max-w-xl truncate" title={item.objeto_compra || undefined}>
                        {item.objeto_compra}
                      </div>
                    </td>
                    <td className="py-2 px-4 border-b whitespace-nowrap">
                      {new Date(item.analise.updated_at).toLocaleString("pt-BR")}
                    </td>
                    <td className="py-2 px-4 border-b text-center">
                      <StatusAnalise analise={item.analise} onVerResultado={() => handleShowResultado(item)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-center p-8 text-gray-500">
              <p>Nenhuma análise concluída encontrada.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
