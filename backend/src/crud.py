
from sqlalchemy.orm import Session
from . import models, schemas
from passlib.context import CryptContext

# Contexto para hashing de senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# --- CRUD para Usuário ---

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password, nickname=user.nickname)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

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

def get_licitacoes(db: Session, skip: int = 0):
    """
    Retorna uma lista de licitações do banco de dados.
    """
    return db.query(models.Licitacao).offset(skip).all()
