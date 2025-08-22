from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# URL de conexão com o banco de dados PostgreSQL.
# Formato: postgresql://usuario:senha@host:porta/nome_do_banco
# Usamos a porta 5433 que mapeamos no docker-compose.yml
DATABASE_URL = "postgresql://licitai_user:licitai_password@localhost:5433/licitai_db"

# O 'engine' é o ponto de entrada para o banco de dados.
engine = create_engine(DATABASE_URL)

# Cada instância de SessionLocal será uma sessão com o banco de dados.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Usaremos esta classe Base para que nossos modelos de dados herdem dela.
Base = declarative_base()

# Função para obter uma sessão do banco de dados por requisição
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
