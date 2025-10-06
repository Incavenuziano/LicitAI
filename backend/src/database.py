from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import psycopg2
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    # Carrega .env do cwd (sem sobrescrever variÃ¡veis jÃ¡ definidas)
    load_dotenv(override=False)
    # TambÃ©m tenta backend/.env relativo a este arquivo (quando executar a partir da raiz)
    backend_env = Path(__file__).resolve().parent.parent / ".env"
    if backend_env.exists():
        load_dotenv(backend_env, override=False)
except Exception:
    pass

# Parâmetros via variáveis de ambiente, com defaults compatíveis com seu setup
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
DB_NAME = os.getenv("POSTGRES_DB", "licitai")
DB_USER = os.getenv("POSTGRES_USER", "licitai_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_TIMEOUT = int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "5"))

# Validação de segurança: a senha do banco NUNCA deve ser nula ou vazia
if not DB_PASS:
    raise ValueError("A variável de ambiente POSTGRES_PASSWORD não está definida. A aplicação não pode iniciar sem a senha do banco de dados.")


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        client_encoding="utf8",
        connect_timeout=DB_TIMEOUT,
    )


# A URL Ã© genÃ©rica; o "creator" cuida da conexÃ£o real usando psycopg2
print(f"[DB] DSN -> host={DB_HOST} port={DB_PORT} db={DB_NAME} user={DB_USER} timeout={DB_TIMEOUT}s")
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
