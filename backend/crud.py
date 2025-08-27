from sqlalchemy.orm import Session
import models, schemas # Importação corrigida
from passlib.context import CryptContext

# Contexto para hashing de senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

# --- CRUD para Usuário ---

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Função para obter um usuário pelo ID
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

# Função para obter múltiplos usuários
def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

# Função para atualizar um usuário existente (comentada)
# def update_user(db: Session, user_id: int, user: schemas.UserUpdate):
#     db_user = db.query(models.User).filter(models.User.id == user_id).first()
#     if db_user:
#         if user.email is not None:
#             db_user.email = user.email
#         if user.password is not None:
#             db_user.hashed_password = user.password
#         if user.is_active is not None:
#             db_user.is_active = user.is_active
#         db.commit()
#         db.refresh(db_user)
#     return db_user

# Função para deletar um usuário
def delete_user(db: Session, user_id: int):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
        return {"message": "User deleted successfully"}
    return None

# --- CRUD para Licitação ---

def create_licitacao(db: Session, licitacao: schemas.LicitacaoCreate) -> models.Licitacao:
    """
    Cria uma nova licitação no banco de dados.
    Evita duplicatas verificando se o numero_controle_pncp já existe.
    """
    db_licitacao = db.query(models.Licitacao).filter(models.Licitacao.numero_controle_pncp == licitacao.numero_controle_pncp).first()
    if db_licitacao:
        return db_licitacao # Retorna a licitação existente se for encontrada
    
    db_licitacao = models.Licitacao(**licitacao.dict())
    db.add(db_licitacao)
    db.commit()
    db.refresh(db_licitacao)
    return db_licitacao

def get_licitacoes(db: Session, skip: int = 0, limit: int = 100):
    """
    Retorna uma lista de licitações do banco de dados, com paginação.
    """
    return db.query(models.Licitacao).offset(skip).limit(limit).all()