import { Licitacao } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface LicitacaoFilters {
  q?: string;
  uf?: string;
  skip?: number;
  limit?: number;
}

export const getLicitacoes = async (filters: LicitacaoFilters = {}): Promise<Licitacao[]> => {
  try {
    const params = new URLSearchParams();
    if (filters.q) params.append('q', filters.q);
    if (filters.uf) params.append('uf', filters.uf);
    if (typeof filters.skip === 'number') params.append('skip', String(filters.skip));
    if (typeof filters.limit === 'number') params.append('limit', String(filters.limit));
    const qs = params.toString();
    const url = `${API_URL}/licitacoes${qs ? `?${qs}` : ''}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Erro na API: ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? (data as Licitacao[]) : [];
  } catch (e) {
    console.error('Falha ao buscar licitações:', e);
    return [];
  }
};

export const getLicitacaoById = async (id: number): Promise<Licitacao | null> => {
  try {
    const res = await fetch(`${API_URL}/licitacoes/${id}`);
    if (!res.ok) {
      if (res.status === 404) return null;
      throw new Error(`Erro na API: ${res.status}`);
    }
    return await res.json();
  } catch (e) {
    console.error('Falha ao buscar licitação:', e);
    return null;
  }
};

export const requestAnalises = async (licitacao_ids: number[]): Promise<any> => {
  const res = await fetch(`${API_URL}/analises/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ licitacao_ids }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || 'Falha ao solicitar análises');
  }
  return res.json();
};

export interface BuscarLicitacoesPayload {
  data_inicio?: string;
  data_fim?: string;
  uf?: string;
  codigo_modalidade?: number;
  tamanho_pagina?: number;
}

export const buscarLicitacoes = async (payload: BuscarLicitacoesPayload): Promise<any> => {
  const res = await fetch(`${API_URL}/buscar_licitacoes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || 'Falha ao buscar licitações');
  }
  return res.json();
};

// RAG endpoints (podem retornar 404 se backend não expuser)
export const ragIndexar = async (licitacaoId: number): Promise<{ indexed_chunks: number } | null> => {
  try {
    const res = await fetch(`${API_URL}/rag/indexar/${licitacaoId}`, { method: 'POST' });
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.error('ragIndexar failed', e);
    return null;
  }
};

export const ragPerguntar = async (
  licitacaoId: number,
  question: string,
  top_k: number = 4,
): Promise<{ results: { score: number; chunk: string }[] }> => {
  const res = await fetch(`${API_URL}/rag/perguntar/${licitacaoId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k }),
  });
  if (!res.ok) {
    return { results: [] };
  }
  return res.json();
};

// Estatísticas (opcional)
export interface StatsUF {
  uf: string;
  total: number;
}

export const getStatsLicitacoesPorUf = async (): Promise<StatsUF[]> => {
  try {
    const res = await fetch(`${API_URL}/stats/licitacoes-por-uf`);
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? (data as StatsUF[]) : [];
  } catch (e) {
    console.error('Falha ao buscar estatísticas por UF:', e);
    return [];
  }
};

