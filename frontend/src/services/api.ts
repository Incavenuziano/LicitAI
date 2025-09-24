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
export const getAnalisesTotal = async (): Promise<number> => {
  try {
    const res = await fetch(`${API_URL}/stats/analises`);
    if (!res.ok) return 0;
    const data = await res.json();
    const total = Number(data?.total ?? 0);
    return Number.isFinite(total) ? total : 0;
  } catch (e) {
    console.error("Falha ao buscar total de análises:", e);
    return 0;
  }
};


// Anexos
export const deleteAnexosPorLicitacao = async (licitacaoId: number): Promise<{ deleted: number }> => {
  const res = await fetch(`${API_URL}/licitacoes/${licitacaoId}/anexos`, { method: 'DELETE' });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `Falha ao apagar anexos da licitação ${licitacaoId}`);
  }
  return res.json();
};

// Oportunidades ativas (PNCP propostas em aberto)
export type OportunidadesPayload = {
  amplo?: boolean;
  uf?: string;
  data_inicio?: string;
  data_fim?: string;
  codigo_modalidade?: number;
  pagina?: number;
  tamanho_pagina?: number;
  total_days?: number;
  step_days?: number;
  ufs?: string[];
  modal_codes?: number[];
  page_limit?: number;
  data_fim_ref?: string;
};

export const getOportunidadesAtivas = async (payload: OportunidadesPayload): Promise<any[]> => {
  const res = await fetch(`${API_URL}/oportunidades/ativas`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || 'Falha ao consultar oportunidades ativas');
  }
  const data = await res.json();
  return Array.isArray(data) ? data : (data?.data ?? []);
};

export const salvarLicitacoesDireto = async (items: any[]): Promise<any> => {
  const res = await fetch(`${API_URL}/licitacoes/salvar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(items),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || 'Falha ao salvar licitações');
  }
  return res.json();
};

// Lista dinâmica de modalidades (descoberta via backend)
export type ModalidadeInfo = { code: number; label: string };
export const getPncpModalidades = async (): Promise<ModalidadeInfo[]> => {
  const res = await fetch(`${API_URL}/pncp/modalidades`);
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? (data as ModalidadeInfo[]) : [];
};

// Série histórica de preços
export type SeriePrecosPoint = { date: string; value: number; fonte: string };
export type SeriePrecosResponse = { mode: string; series: SeriePrecosPoint[]; stats: { count: number; min: number | null; max: number | null; mean: number | null } };

export const getSeriePrecos = async (payload: { cnpj?: string; descricao?: string; fonte?: string; data_inicio?: string; data_fim?: string }): Promise<SeriePrecosResponse> => {
  const res = await fetch(`${API_URL}/precos/serie`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || 'Falha ao obter série de preços');
  }
  return res.json();
};

// Pesquisa agregada de preços por item (resumo)
export type PesquisaPrecoResponse = {
  query: string;
  fonte: string;
  precos_encontrados: number;
  stats: { min: number | null; max: number | null; mean: number | null; median: number | null };
  detalhes: { referencia_id: string | number; preco: number }[];
};

export const pesquisarPrecosPorItem = async (descricao: string, fonte: 'comprasgov'|'pncp'|'ambas'='comprasgov'): Promise<PesquisaPrecoResponse> => {
  const url = new URL(`${API_URL}/pesquisa/precos_por_item`);
  url.searchParams.set('descricao', descricao);
  url.searchParams.set('fonte', fonte);
  const res = await fetch(url.toString());
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || 'Falha na pesquisa de preços');
  }
  const data = await res.json();
  // mapear detalhes para {referencia_id, preco} se necessário
  const detalhes = Array.isArray(data?.detalhes)
    ? data.detalhes.map((d: any) => ({ referencia_id: d.licitacao_id ?? d.contrato_id ?? d.fonte ?? '—', preco: Number(d.preco ?? d.valor ?? d) }))
    : [];
  return {
    query: data?.query ?? descricao,
    fonte: data?.fonte ?? fonte,
    precos_encontrados: data?.precos_encontrados ?? (detalhes?.length ?? 0),
    stats: data?.stats ?? { min: null, max: null, mean: null, median: null },
    detalhes,
  } as PesquisaPrecoResponse;
};

export type PrecoVencedorResponse = {
  base: { id: number; numero_controle_pncp: string | null; objeto_compra: string | null };
  similares_considerados: number;
  precos_encontrados: number;
  stats: { count: number; min: number | null; max: number | null; mean: number | null; median: number | null };
  detalhes: { licitacao_id: number; preco: number }[];
};

export const getPrecosVencedores = async (
  licitacaoId: number,
  fonte: 'comprasgov' | 'pncp' | 'ambas' = 'comprasgov',
  top_k: number = 20,
): Promise<PrecoVencedorResponse> => {
  const params = new URLSearchParams();
  if (fonte) params.set('fonte', fonte);
  if (typeof top_k === 'number' && Number.isFinite(top_k)) {
    params.set('top_k', String(top_k));
  }
  const qs = params.toString();
  const url = `${API_URL}/licitacoes/${licitacaoId}/precos_vencedores${qs ? `?${qs}` : ''}`;
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || 'Falha ao buscar precos vencedores');
  }
  return res.json();
};

// DocBox

// DocBox (upload e associação)
export type DocBoxItem = { id: number; filename: string; size_bytes: number; sha256: string; created_at: string | null; meta?: string | null };

export const docboxList = async (licitacaoId: number): Promise<DocBoxItem[]> => {
  const res = await fetch(`${API_URL}/docbox/${licitacaoId}`);
  if (!res.ok) return [];
  return res.json();
};

export const docboxUpload = async (licitacaoId: number, file: File, tag?: string, desc?: string): Promise<DocBoxItem> => {
  const form = new FormData();
  form.append('licitacao_id', String(licitacaoId));
  form.append('file', file);
  if (tag) form.append('tag', tag);
  if (desc) form.append('desc', desc);
  const res = await fetch(`${API_URL}/docbox/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || 'Falha no upload do DocBox');
  }
  return res.json();
};

export const docboxDelete = async (anexoId: number): Promise<{ deleted: boolean }> => {
  const res = await fetch(`${API_URL}/docbox/${anexoId}`, { method: 'DELETE' });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || 'Falha ao remover documento');
  }
  return res.json();
};
