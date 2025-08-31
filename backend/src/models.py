from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    nickname = Column(String, nullable=True)

class Licitacao(Base):
    __tablename__ = "licitacoes"
    id = Column(Integer, primary_key=True, index=True)
    numero_controle_pncp = Column(String, unique=True, index=True, nullable=False)
    ano_compra = Column(Integer)
    sequencial_compra = Column(Integer)
    modalidade_nome = Column(String)
    objeto_compra = Column(Text)
    valor_total_estimado = Column(Numeric(15, 2))
    orgao_entidade_nome = Column(String)
    unidade_orgao_nome = Column(String)
    uf = Column(String(2))
    municipio_nome = Column(String)
    data_publicacao_pncp = Column(DateTime)
    data_encerramento_proposta = Column(DateTime)
    link_sistema_origem = Column(String)
    
    # Relacionamento com a tabela de Análises
    analises = relationship("Analise", back_populates="licitacao")

class Analise(Base):
    __tablename__ = "analises"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, nullable=False, default="Pendente")
    resultado = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    licitacao_id = Column(Integer, ForeignKey("licitacoes.id"))
    
    # Relacionamento com a tabela de Licitações
    licitacao = relationship("Licitacao", back_populates="analises")


class EditalEmbedding(Base):
    __tablename__ = 'edital_embeddings'
    id = Column(Integer, primary_key=True, index=True)
    licitacao_id = Column(Integer, ForeignKey('licitacoes.id'), index=True, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=False)  # JSON com a lista de floats
