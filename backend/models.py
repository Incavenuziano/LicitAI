from sqlalchemy import Boolean, Column, Integer, String
from .database import Base

# Esta é a nossa classe modelo para a tabela de usuários.
# O SQLAlchemy usará isso para criar a tabela "users" no banco de dados.
class User(Base):
    __tablename__ = "users"

    # Colunas da nossa tabela
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
