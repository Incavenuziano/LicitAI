# backend/src/update_nickname.py
import sys
import os
from sqlalchemy.orm import Session

# Adiciona o diretório raiz do projeto ao sys.path para permitir importações
# Isso é necessário para executar este script diretamente
# Ajuste o número de os.path.dirname para subir os níveis corretos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from src.database import get_db
from src import crud

def update_user_nickname(db: Session, email: str, nickname: str):
    """
    Atualiza o nickname de um usuário existente.
    """
    db_user = crud.get_user_by_email(db, email=email)
    if db_user:
        print(f"Usuário encontrado: {db_user.email}. Atualizando nickname para '{nickname}'...")
        db_user.nickname = nickname
        db.commit()
        db.refresh(db_user)
        print("Nickname atualizado com sucesso!")
        print(f"Email: {db_user.email}, Novo Nickname: {db_user.nickname}")
        return db_user
    else:
        print(f"Usuário com email {email} não encontrado.")
        return None

if __name__ == "__main__":
    # Configurações
    USER_EMAIL_TO_UPDATE = "daniloamalmeida@gmail.com"
    NEW_NICKNAME = "Danilo"

    print("Iniciando script de atualização de nickname...")
    # Obtém uma sessão do banco de dados
    db_session_gen = get_db()
    db = next(db_session_gen)
    
    try:
        # Executa a atualização
        update_user_nickname(db, email=USER_EMAIL_TO_UPDATE, nickname=NEW_NICKNAME)
    finally:
        # Fecha a sessão
        db.close()
        print("Sessão do banco de dados fechada.")
