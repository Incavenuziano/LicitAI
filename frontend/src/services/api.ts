import { Licitacao } from '@/types';
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const getLicitacoes = async (): Promise<Licitacao[]> => {
  try {
    // Estamos buscando da URL da nossa API backend que está rodando na porta 8000
    const response = await fetch(`${API_URL}/licitacoes`);
    
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
  const response = await fetch(`${API_URL}/analises/`, {
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

export interface BuscarLicitacoesPayload {
  data_inicio?: string;
  data_fim?: string;
  uf?: string;
  codigo_modalidade?: number;
  tamanho_pagina?: number;
}

export const buscarLicitacoes = async (payload: BuscarLicitacoesPayload): Promise<any> => {
  const response = await fetch(`${API_URL}/buscar_licitacoes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Erro desconhecido na busca' }));
    throw new Error(errorData.detail || 'Erro ao buscar licitações');
  }
  return response.json();
};



