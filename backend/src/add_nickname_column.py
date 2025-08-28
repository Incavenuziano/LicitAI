import sys
import os
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

# Adiciona o diretório pai ao sys.path para permitir importações relativas
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import engine

print("Iniciando script para adicionar coluna 'nickname'...")

with engine.connect() as connection:
    transaction = connection.begin()
    try:
        print("Executando: ALTER TABLE users ADD COLUMN nickname VARCHAR")
        connection.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR"))
        transaction.commit()
        print("SUCESSO: Coluna 'nickname' adicionada à tabela 'users'.")
    except ProgrammingError as e:
        # Código de erro para "duplicate_column" no psycopg2
        if hasattr(e.orig, 'pgcode') and e.orig.pgcode == '42701':
            print("INFO: A coluna 'nickname' já existe na tabela 'users'. Nenhuma alteração foi feita.")
            transaction.rollback()
        else:
            print(f"ERRO: Ocorreu um erro ao adicionar a coluna: {e}")
            transaction.rollback()
            raise
    except Exception as e:
        print(f"ERRO INESPERADO: {e}")
        transaction.rollback()
        raise

print("Script finalizado.")
