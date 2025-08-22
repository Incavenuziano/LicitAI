from sqlalchemy.orm import Session
from . import models, schemas

# Função para criar um novo usuário no banco de dados
def create_user(db: Session, user: schemas.UserCreate):
    # Cria uma instância do modelo User com os dados fornecidos
    # ATENÇÃO: Em uma aplicação real, a senha seria HASHED antes de ser salva!
    db_user = models.User(email=user.email, hashed_password=user.password)
    db.add(db_user) # Adiciona o novo usuário à sessão do banco de dados
    db.commit() # Confirma a transação, salvando o usuário no banco
    db.refresh(db_user) # Atualiza a instância com os dados gerados pelo banco (ex: id)
    return db_user

# Função para obter um usuário pelo ID
def get_user(db: Session, user_id: int):
    # Consulta o banco de dados para encontrar um usuário pelo ID
    return db.query(models.User).filter(models.User.id == user_id).first()

# Função para obter um usuário pelo email
def get_user_by_email(db: Session, email: str):
    # Consulta o banco de dados para encontrar um usuário pelo email
    return db.query(models.User).filter(models.User.email == email).first()

# Função para obter múltiplos usuários
def get_users(db: Session, skip: int = 0, limit: int = 100):
    # Consulta o banco de dados para obter uma lista de usuários, com paginação
    return db.query(models.User).offset(skip).limit(limit).all()

# Função para atualizar um usuário existente
def update_user(db: Session, user_id: int, user: schemas.UserUpdate):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        # Atualiza os campos se eles forem fornecidos no objeto de atualização
        if user.email is not None:
            db_user.email = user.email
        # ATENÇÃO: Em uma aplicação real, a senha seria HASHED antes de ser salva!
        if user.password is not None:
            db_user.hashed_password = user.password
        if user.is_active is not None:
            db_user.is_active = user.is_active
        db.commit()
        db.refresh(db_user)
    return db_user

# Função para deletar um usuário
def delete_user(db: Session, user_id: int):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
        return {"message": "User deleted successfully"}
    return None
