from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func
from . import models, schemas
from passlib.context import CryptContext
from datetime import datetime
import logging
from pathlib import Path

logger = logging.getLogger("crud")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --- Users ---
def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    hashed = pwd_context.hash(user.password)
    db_user = models.User(
        email=user.email.lower().strip(),
        hashed_password=hashed,
        nickname=user.nickname,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False



def update_licitacao_fields_if_empty(
    db: Session, licitacao_id: int, **fields
) -> models.Licitacao | None:
    """Atualiza campos de uma licitacao somente quando estiverem vazios ou com placeholders."""
    lic = db.query(models.Licitacao).filter(models.Licitacao.id == licitacao_id).first()
    if not lic:
        return None

    placeholders: dict[str, set[str]] = {
        "objeto_compra": {"upload manual de edital"},
        "orgao_entidade_nome": set(),
    }

    changed = False
    for attr, value in fields.items():
        if value is None or not hasattr(lic, attr):
            continue

        current = getattr(lic, attr)
        is_empty = current is None
        if isinstance(current, str):
            normalized = current.strip().lower()
            placeholder_values = placeholders.get(attr, set())
            is_empty = (not normalized) or (normalized in placeholder_values)
        if not is_empty:
            continue

        setattr(lic, attr, value)
        changed = True

    if changed:
        db.add(lic)
        db.commit()
        db.refresh(lic)
    return lic




# --- LicitaÃ§Ãµes ---
def get_licitacoes(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    q: str | None = None,
    uf: str | None = None,
    has_analise: bool | None = None,
):
    query = db.query(models.Licitacao).options(selectinload(models.Licitacao.analises))
    if q:
        query = query.filter(models.Licitacao.objeto_compra.ilike(f"%{q}%"))
    if uf:
        query = query.filter(models.Licitacao.uf == uf.upper())
    if has_analise is not None:
        query = query.outerjoin(models.Analise)
        if has_analise:
            query = query.filter(models.Analise.id.isnot(None))
        else:
            query = query.filter(models.Analise.id.is_(None))
        query = query.distinct(models.Licitacao.id)
    return query.order_by(models.Licitacao.data_publicacao_pncp.desc()).offset(skip).limit(limit).all()


def get_licitacao(db: Session, licitacao_id: int) -> models.Licitacao | None:
    return (
        db.query(models.Licitacao)
        .options(selectinload(models.Licitacao.analises))
        .filter(models.Licitacao.id == licitacao_id)
        .first()
    )


def get_licitacao_by_numero_controle(
    db: Session, numero_controle_pncp: str
) -> models.Licitacao | None:
    if not numero_controle_pncp:
        return None
    return (
        db.query(models.Licitacao)
        .options(selectinload(models.Licitacao.analises))
        .filter(models.Licitacao.numero_controle_pncp == numero_controle_pncp)
        .first()
    )


def get_licitacao_count_by_uf(db: Session):
    """Conta o nÃºmero de licitaÃ§Ãµes por UF, retornando as que tÃªm UF definida."""
    return (
        db.query(models.Licitacao.uf, func.count(models.Licitacao.id).label("total"))
        .filter(models.Licitacao.uf != None)
        .group_by(models.Licitacao.uf)
        .order_by(func.count(models.Licitacao.id).desc())
        .all()
    )




def get_total_analises(db: Session) -> int:
    return db.query(func.count(models.Analise.id)).scalar() or 0

# --- AnÃ¡lises & Anexos ---

def create_licitacao(db: Session, licitacao: schemas.LicitacaoCreate) -> models.Licitacao:
    """Cria ou atualiza uma licitação com base no numero_controle_pncp."""
    dados = licitacao.model_dump(exclude_unset=True)
    numero = dados.get("numero_controle_pncp")
    query = db.query(models.Licitacao)
    if numero:
        existente = query.filter(models.Licitacao.numero_controle_pncp == numero).first()
    else:
        existente = None

    if existente:
        for campo, valor in dados.items():
            setattr(existente, campo, valor)
        db.add(existente)
        db.commit()
        db.refresh(existente)
        return existente

    nova = models.Licitacao(**dados)
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return nova


def delete_licitacao_completa(db: Session, licitacao_id: int) -> bool:
    """Remove licitação e dependências (análises, anexos, embeddings)."""
    exists = db.query(models.Licitacao.id).filter(models.Licitacao.id == licitacao_id).scalar()
    if not exists:
        return False

    anexos = (
        db.query(models.Anexo)
        .filter(models.Anexo.licitacao_id == licitacao_id)
        .all()
    )
    for anexo in anexos:
        try:
            if anexo.local_path:
                path = Path(anexo.local_path)
                if path.exists():
                    path.unlink()
        except Exception:
            logger.warning(
                "[crud] falha ao remover arquivo de anexo licitacao_id=%s path=%s",
                licitacao_id,
                getattr(anexo, "local_path", None),
            )

    db.query(models.EditalEmbedding).filter(models.EditalEmbedding.licitacao_id == licitacao_id).delete(synchronize_session=False)
    db.query(models.Anexo).filter(models.Anexo.licitacao_id == licitacao_id).delete(synchronize_session=False)
    db.query(models.Analise).filter(models.Analise.licitacao_id == licitacao_id).delete(synchronize_session=False)

    deleted = db.query(models.Licitacao).filter(models.Licitacao.id == licitacao_id).delete(synchronize_session=False)
    db.commit()
    return bool(deleted)


def create_licitacao_manual(
    db: Session,
    numero_controle_pncp: str,
    *,
    objeto_compra: str | None = None,
    orgao_entidade_nome: str | None = None,
    link_sistema_origem: str | None = None,
    uf: str | None = None,
    municipio_nome: str | None = None,
    data_publicacao_pncp: datetime | None = None,
    data_encerramento_proposta: datetime | None = None,
) -> models.Licitacao:
    lic = models.Licitacao(
        numero_controle_pncp=numero_controle_pncp,
        objeto_compra=objeto_compra,
        orgao_entidade_nome=orgao_entidade_nome,
        link_sistema_origem=link_sistema_origem,
        uf=(uf.upper() if uf else None),
        municipio_nome=municipio_nome,
        data_publicacao_pncp=data_publicacao_pncp or datetime.utcnow(),
        data_encerramento_proposta=data_encerramento_proposta,
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return lic


def create_anexo(
    db: Session,
    *,
    licitacao_id: int | None,
    source: str,
    filename: str | None = None,
    local_path: str | None = None,
    url: str | None = None,
    content_type: str | None = None,
    size_bytes: int | None = None,
    sha256: str | None = None,
    score: int | None = None,
    status: str = "saved",
    error: str | None = None,
) -> models.Anexo:
    an = models.Anexo(
        licitacao_id=licitacao_id,
        source=source,
        url=url,
        filename=filename,
        local_path=local_path,
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        score=score,
        status=status,
        error=error,
    )
    db.add(an)
    db.commit()
    db.refresh(an)
    return an


def get_principal_anexo(db: Session, licitacao_id: int) -> models.Anexo | None:
    return (
        db.query(models.Anexo)
        .filter(
            models.Anexo.licitacao_id == licitacao_id,
            models.Anexo.local_path.isnot(None),
        )
        .order_by(models.Anexo.score.desc(), models.Anexo.created_at.desc())
        .first()
    )


def create_licitacao_analise(db: Session, licitacao_id: int) -> models.Analise:
    lic = get_licitacao(db, licitacao_id)
    if lic is None:
        raise ValueError(f"Licitacao {licitacao_id} nÃ£o encontrada")
    analise = models.Analise(status="Pendente", licitacao_id=licitacao_id)
    db.add(analise)
    db.commit()
    db.refresh(analise)
    logger.info(f"[crud] create_licitacao_analise analise_id={analise.id} licitacao_id={licitacao_id} status=Pendente")
    return analise


def get_analise(db: Session, analise_id: int) -> models.Analise | None:
    return db.query(models.Analise).filter(models.Analise.id == analise_id).first()


def update_analise(
    db: Session, analise_id: int, status: str | None = None, resultado: str | None = None
) -> models.Analise | None:
    """Atualiza uma anÃ¡lise, permitindo alterar status e/ou resultado."""
    analise = get_analise(db, analise_id)
    if not analise:
        return None

    if status is not None:
        logger.info(f"[crud] update_analise analise_id={analise_id} status={status}")
        analise.status = status
    if resultado is not None:
        logger.info(f"[crud] update_analise analise_id={analise_id} resultado_len={len(resultado)}")
        analise.resultado = resultado

    db.add(analise)
    db.commit()
    db.refresh(analise)
    return analise


def update_analise_status(db: Session, analise_id: int, status: str) -> models.Analise | None:
    analise = get_analise(db, analise_id)
    if not analise:
        return None
    logger.info(f"[crud] update_analise_status analise_id={analise_id} status={status}")
    analise.status = status
    db.add(analise)
    db.commit()
    db.refresh(analise)
    return analise


def set_analise_resultado(db: Session, analise_id: int, resultado: str, status: str = "Concluido") -> models.Analise | None:
    analise = get_analise(db, analise_id)
    if not analise:
        return None
    analise.resultado = resultado
    analise.status = status
    logger.info(f"[crud] set_analise_resultado analise_id={analise_id} status={status} resultado_len={len(resultado)}")
    db.add(analise)
    db.commit()
    db.refresh(analise)
    return analise








def search_licitacoes_by_objeto(db: Session, query: str):
    if not query:
        return []
    pattern = f"%{query}%"
    return (
        db.query(models.Licitacao)
        .filter(models.Licitacao.objeto_compra.ilike(pattern))
        .all()

    )
