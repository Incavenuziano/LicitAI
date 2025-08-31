export type Analise = {
  id: number;
  licitacao_id: number;
  status: string;
  resultado: string | null;
  created_at: string;
  updated_at: string;
};

export type Licitacao = {
  id: number;
  numero_controle_pncp: string;
  ano_compra: number | null;
  sequencial_compra: number | null;
  modalidade_nome: string | null;
  objeto_compra: string | null;
  valor_total_estimado: string | null;
  orgao_entidade_nome: string | null;
  unidade_orgao_nome: string | null;
  uf: string | null;
  municipio_nome: string | null;
  data_publicacao_pncp: string | null;
  data_encerramento_proposta: string | null;
  link_sistema_origem: string | null;
  analises: Analise[]; // Array de análises associadas
};

// --- Tipos para agente de preço vencedor ---
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

// --- Tipos para Dashboard ---
export type DashboardKpis = {
  novas_hoje: number;
  valor_total_aberto: number;
  analises_concluidas: number;
};

export type DashboardUF = { uf: string; count: number };
export type DashboardTipo = { tipo: 'Serviço' | 'Aquisição' | 'Outros'; count: number };

export type DashboardSummary = {
  kpis: DashboardKpis;
  by_uf: DashboardUF[];
  by_tipo: DashboardTipo[];
};
