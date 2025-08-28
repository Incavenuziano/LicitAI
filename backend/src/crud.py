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
    db_licitacao = db.query(models.Licitacao).filter(models.Licitacao.numero_controle_pncp == licitacao.numero_controle_pncp).first()
    if db_licitacao:
        return db_licitacao
    db_licitacao = models.Licitacao(**licitacao.dict())
    db.add(db_licitacao)
    db.commit()
    db.refresh(db_licitacao)
    return db_licitacao

def get_licitacoes(db: Session, skip: int = 0):
    return db.query(models.Licitacao).offset(skip).all()

# --- CRUD para Análise ---

def get_analise(db: Session, analise_id: int):
    """
    Busca uma análise pelo seu ID.
    """
    return db.query(models.Analise).filter(models.Analise.id == analise_id).first()

def create_licitacao_analise(db: Session, licitacao_id: int) -> models.Analise:
    """
    Cria um novo registro de análise para uma licitação com status 'Pendente'.
    Se já existir uma análise para a licitação, a retorna.
    """
    db_analise = db.query(models.Analise).filter(models.Analise.licitacao_id == licitacao_id).first()
    if db_analise:
        # Se a análise já existe, talvez queira resetar o status para uma nova análise
        db_analise.status = "Pendente"
        db_analise.resultado = None
        db.commit()
        db.refresh(db_analise)
        return db_analise

    # Cria uma nova se não existir
    db_analise = models.Analise(licitacao_id=licitacao_id, status="Pendente")
    db.add(db_analise)
    db.commit()
    db.refresh(db_analise)
    return db_analise

def update_analise(db: Session, analise_id: int, status: str, resultado: str):
    """
    Atualiza o status e o resultado de uma análise.
    """
    db_analise = get_analise(db, analise_id=analise_id)
    if db_analise:
        db_analise.status = status
        db_analise.resultado = resultado
        db.commit()
        db.refresh(db_analise)
    return db_analise