import { Licitacao } from '@/types';

export const getLicitacoes = async (): Promise<Licitacao[]> => {
  try {
    // Estamos buscando da URL da nossa API backend que está rodando na porta 8000
    const response = await fetch('http://127.0.0.1:8000/licitacoes/');
    
    if (!response.ok) {
      // Se a resposta do servidor não for bem-sucedida, lançamos um erro.
      throw new Error(`Erro na API: ${response.statusText}`);
    }

    const data: Licitacao[] = await response.json();
    return data;

  } catch (error) {
    console.error("Falha ao buscar licitações:", error);
    // Em caso de erro na rede ou na conversão, retornamos um array vazio.
    // Uma aplicação mais complexa poderia tratar este erro de forma mais elegante.
    return [];
  }
};

export const requestAnalises = async (licitacao_ids: number[]): Promise<any> => {
  const response = await fetch('http://localhost:8000/analises/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ licitacao_ids }),
  });

  if (!response.ok) {
    // Lança um erro se a resposta não for bem-sucedida, para que o componente possa tratar.
    const errorData = await response.json().catch(() => ({ detail: 'Erro desconhecido ao solicitar análise' }));
    throw new Error(errorData.detail);
  }

  return response.json();
};