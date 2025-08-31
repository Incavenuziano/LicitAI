import os
from pathlib import Path
import psycopg2

# Tenta carregar variáveis do backend/.env sem sobrescrever variáveis já definidas
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(override=False)  # .env do diretório atual, se existir
    backend_env = Path(__file__).resolve().parent.parent / ".env"
    if backend_env.exists():
        load_dotenv(backend_env, override=False)
except Exception:
    pass


def main():
    print("Current working directory:", os.getcwd())

    # Mesmos defaults do src/database.py
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5433"))
    dbname = os.getenv("POSTGRES_DB", "licitai")
    user = os.getenv("POSTGRES_USER", "licitai_user")
    password = os.getenv("POSTGRES_PASSWORD", "licitai_password")

    dsn = (
        f"host={host} port={port} dbname={dbname} user={user} password={password} "
        "client_encoding=utf8 application_name=LicitAI_Test_Connection"
    )

    print("Attempting to connect with:")
    print(f" - host={host} port={port} dbname={dbname} user={user}")

    try:
        with psycopg2.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                one = cur.fetchone()
                print("Connection successful! Test query result:", one)
    except Exception as e:
        print("An error occurred:", e)


if __name__ == "__main__":
    main()
