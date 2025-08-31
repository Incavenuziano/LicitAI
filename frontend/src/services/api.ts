import { Licitacao } from '@/types';
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const getLicitacoes = async (): Promise<Licitacao[]> => {
  try {
    // Estamos buscando da URL da nossa API backend que estÃ¡ rodando na porta 8000
    const response = await fetch(`${API_URL}/licitacoes`);
    
    if (!response.ok) {
      // Se a resposta do servidor nÃ£o for bem-sucedida, lanÃ§amos um erro.
      throw new Error(`Erro na API: ${response.statusText}`);
    }

    const data: Licitacao[] = await response.json();
    return data;

  } catch (error) {
    console.error("Falha ao buscar licitaÃ§Ãµes:", error);
    // Em caso de erro na rede ou na conversÃ£o, retornamos um array vazio.
    // Uma aplicaÃ§Ã£o mais complexa poderia tratar este erro de forma mais elegante.
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
    // LanÃ§a um erro se a resposta nÃ£o for bem-sucedida, para que o componente possa tratar.
    const errorData = await response.json().catch(() => ({ detail: 'Erro desconhecido ao solicitar anÃ¡lise' }));
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
    throw new Error(errorData.detail || 'Erro ao buscar licitaÃ§Ãµes');
  }
  return response.json();
};

// --- Agente: PreÃ§o vencedor de itens similares ---
export type PrecoStats = {
  count: number;
  min: number | null;
  max: number | null;
  mean: number | null;
  median: number | null;
};

export type PrecoDetalhe = { licitacao_id: number; preco: number };

export type PrecoVencedorResponse = {
  base: { id: number; numero_controle_pncp: string | null; objeto_compra: string | null };
  similares_considerados: number;
  precos_encontrados: number;
  stats: PrecoStats;
  detalhes: PrecoDetalhe[];
};

export const getPrecosVencedores = async (
  licitacaoId: number,
  fonte: 'comprasgov' | 'pncp' | 'ambas' = 'comprasgov',
  top_k: number = 20
): Promise<PrecoVencedorResponse> => {
  const url = new URL(`${API_URL}/agentes/preco_vencedor/${licitacaoId}`);
  url.searchParams.set('top_k', String(top_k));
  if (fonte) url.searchParams.set('fonte', fonte);
  const res = await fetch(url.toString(), { cache: 'no-store' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({} as any));
    throw new Error(err.detail || 'Falha ao consultar preÃ§os vencedores');
  }
  return res.json();
};




// --- RAG: Indexar e Perguntar ---
export type RagResult = {
  licitacao_id: number;
  question: string;
  results: { score: number; chunk: string }[];
};

export const ragIndexar = async (licitacaoId: number): Promise<{ licitacao_id: number; chunks_indexados: number }> => {
  const res = await fetch(`${API_URL}/rag/indexar/${licitacaoId}`, { method: 'POST' });
  if (!res.ok) throw new Error('Falha ao indexar edital');
  return res.json();
};

export const ragPerguntar = async (licitacaoId: number, question: string, top_k: number = 4): Promise<RagResult> => {
  const res = await fetch(`${API_URL}/rag/perguntar/${licitacaoId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, top_k }),
  });
  if (!res.ok) throw new Error('Falha ao consultar RAG');
  return res.json();
};
