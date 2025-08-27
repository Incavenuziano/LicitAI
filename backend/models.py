from sqlalchemy import Column, Integer, String, DateTime, Numeric, Text
from database import Base  # Importa o Base do nosso arquivo database.py

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

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