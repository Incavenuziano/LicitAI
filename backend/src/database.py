from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# A URL de conexão é montada a partir de variáveis de ambiente
# que devem ser definidas no seu ambiente (ex: .env ou docker-compose.yml)
# postgresql://user:password@host/database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/licitai") + "?client_encoding=utf8"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base declarativa para os modelos do SQLAlchemy
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()