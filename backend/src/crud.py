from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from . import models, schemas
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Users ---
def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    hashed = pwd_context.hash(user.password)
    db_user = models.User(email=user.email.lower().strip(), hashed_password=hashed, nickname=user.nickname)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


# --- Licitações ---
def get_licitacoes(
    db: Session, skip: int = 0, limit: int = 100, q: str | None = None, uf: str | None = None
):
    query = db.query(models.Licitacao).options(selectinload(models.Licitacao.analises))
    if q:
        query = query.filter(models.Licitacao.objeto_compra.ilike(f"%{q}%"))
    if uf:
        query = query.filter(models.Licitacao.uf == uf.upper())
    return (
        query.order_by(models.Licitacao.data_publicacao_pncp.desc()).offset(skip).limit(limit).all()
    )


def get_licitacao(db: Session, licitacao_id: int) -> models.Licitacao | None:
    return (
        db.query(models.Licitacao)
        .options(selectinload(models.Licitacao.analises))
        .filter(models.Licitacao.id == licitacao_id)
        .first()
    )


def get_licitacao_count_by_uf(db: Session):
    """Conta o número de licitações por UF, retornando as que têm UF definida."""
    return (
        db.query(models.Licitacao.uf, func.count(models.Licitacao.id).label("total"))
        .filter(models.Licitacao.uf != None)
        .group_by(models.Licitacao.uf)
        .order_by(func.count(models.Licitacao.id).desc())
        .all()
    )


# --- Análises ---
def create_licitacao_analise(db: Session, licitacao_id: int) -> models.Analise:
    lic = get_licitacao(db, licitacao_id)
    if lic is None:
        raise ValueError(f"Licitacao {licitacao_id} não encontrada")
    analise = models.Analise(status="Pendente", licitacao_id=licitacao_id)
    db.add(analise)
    db.commit()
    db.refresh(analise)
    return analise


def get_analise(db: Session, analise_id: int) -> models.Analise | None:
    return db.query(models.Analise).filter(models.Analise.id == analise_id).first()


def update_analise_status(db: Session, analise_id: int, status: str) -> models.Analise | None:
    analise = get_analise(db, analise_id)
    if not analise:
        return None
    analise.status = status
    db.add(analise)
    db.commit()
    db.refresh(analise)
    return analise


def set_analise_resultado(db: Session, analise_id: int, resultado: str, status: str = "Concluído") -> models.Analise | None:
    analise = get_analise(db, analise_id)
    if not analise:
        return None
    analise.resultado = resultado
    analise.status = status
    db.add(analise)
    db.commit()
    db.refresh(analise)
    return analise

