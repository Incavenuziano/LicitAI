from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

# --- Esquemas para Usuário ---

class UserBase(BaseModel):
    email: str
    nickname: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int

    class Config:
        from_attributes = True

# --- Esquemas para Análise ---
# Definido antes de Licitação para que Licitação possa referenciá-lo

class AnaliseBase(BaseModel):
    status: str = "Pendente"
    resultado: Optional[str] = None

class AnaliseCreate(AnaliseBase):
    licitacao_id: int

class Analise(AnaliseBase):
    id: int
    licitacao_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Esquemas para Licitação ---

class LicitacaoBase(BaseModel):
    numero_controle_pncp: str
    ano_compra: Optional[int] = None
    sequencial_compra: Optional[int] = None
    modalidade_nome: Optional[str] = None
    objeto_compra: Optional[str] = None
    valor_total_estimado: Optional[Decimal] = None
    orgao_entidade_nome: Optional[str] = None
    unidade_orgao_nome: Optional[str] = None
    uf: Optional[str] = None
    municipio_nome: Optional[str] = None
    data_publicacao_pncp: Optional[datetime] = None
    data_encerramento_proposta: Optional[datetime] = None
    link_sistema_origem: Optional[str] = None

class LicitacaoCreate(LicitacaoBase):
    pass

class Licitacao(LicitacaoBase):
    id: int
    analises: List[Analise] = [] # Relacionamento com Análises

    class Config:
        from_attributes = True

# --- Esquemas para Requisições --- 

class AnaliseRequest(BaseModel):
    licitacao_ids: List[int]
