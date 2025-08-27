from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import psycopg2
import os

# --- Nova abordagem de conexão para evitar bug de unicode ---
# Em vez de usar uma URL, usamos uma função "creator" para passar
# os parâmetros de conexão separadamente.

def get_connection():
    return psycopg2.connect(
        host="localhost",
        port="5433",
        database="licitai",
        user="licitai_user",
        password="licitai_password", # Usando a senha padrão do arquivo original
        client_encoding="utf8"
    )

# A URL agora é genérica, pois o "creator" cuidará da conexão.
engine = create_engine("postgresql+psycopg2://", creator=get_connection)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base declarativa para os modelos do SQLAlchemy
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
