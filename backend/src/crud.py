from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func
from . import models, schemas
from passlib.context import CryptContext

# ... (resto do arquivo até o final da seção de Licitação)

def get_licitacoes(db: Session, skip: int = 0, limit: int = 100, q: str | None = None, uf: str | None = None):
    query = db.query(models.Licitacao).options(selectinload(models.Licitacao.analises))

    if q:
        query = query.filter(models.Licitacao.objeto_compra.ilike(f"%{q}%"))
    
    if uf:
        query = query.filter(models.Licitacao.uf == uf.upper())

    return query.order_by(models.Licitacao.data_publicacao_pncp.desc()).offset(skip).limit(limit).all()

def get_licitacao_count_by_uf(db: Session):
    """Conta o número de licitações por UF, retornando as que têm UF definida."""
    return db.query(
        models.Licitacao.uf,
        func.count(models.Licitacao.id).label("total")
    ).filter(models.Licitacao.uf != None).group_by(models.Licitacao.uf).order_by(func.count(models.Licitacao.id).desc()).all()


# --- CRUD para Análise ---
# ... (resto do arquivo)