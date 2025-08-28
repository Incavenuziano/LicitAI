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