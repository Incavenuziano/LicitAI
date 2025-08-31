import json
import math
import os
from typing import List, Tuple, Optional

from sqlalchemy.orm import Session

from .models import EditalEmbedding, Licitacao

try:  # Optional until installed
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore


def _ensure_genai():
    if genai is None:
        raise RuntimeError("google-generativeai não instalado. pip install google-generativeai")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Defina GEMINI_API_KEY ou GOOGLE_API_KEY no ambiente/.env")
    genai.configure(api_key=api_key)


def embed_texts(texts: List[str], model: str = "text-embedding-004") -> List[List[float]]:
    """Gera embeddings usando Gemini. Retorna lista de vetores float."""
    _ensure_genai()
    # API supports batching
    result = genai.embed_content(model=model, content=texts)
    # The response shape can be {'embedding': [...]} or {'embeddings': {'values': [...]}}
    if isinstance(result, dict):
        if "embedding" in result:
            # Single input case mistakenly? Normalize to list
            emb = result["embedding"]
            return [list(emb)]
        if "embeddings" in result and isinstance(result["embeddings"], list):
            return [list(x["values"]) if isinstance(x, dict) and "values" in x else list(x) for x in result["embeddings"]]
    # Fallback
    try:
        values = result.embeddings
        return [list(x.values) for x in values]
    except Exception:
        raise RuntimeError("Formato inesperado de retorno do embed_content")


def cosine(a: List[float], b: List[float]) -> float:
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return s / (na * nb)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> List[str]:
    text = text.replace("\r\n", "\n")
    chunks = []
    i = 0
    while i < len(text):
        chunk = text[i : i + chunk_size]
        chunks.append(chunk)
        i += max(1, chunk_size - overlap)
    return chunks


def index_licitacao(db: Session, licitacao: Licitacao, text_extractor) -> int:
    """Extrai texto do edital via callable text_extractor(licitacao) -> str, cria chunks e indexa.
    Retorna quantidade de chunks indexados.
    """
    texto = text_extractor(licitacao)
    if not texto:
        return 0
    chunks = chunk_text(texto)
    embs = embed_texts(chunks)
    count = 0
    for idx, (ch, emb) in enumerate(zip(chunks, embs)):
        item = EditalEmbedding(
            licitacao_id=licitacao.id,
            chunk_index=idx,
            content=ch,
            embedding=json.dumps(emb),
        )
        db.add(item)
        count += 1
    db.commit()
    return count


def query_licitacao(db: Session, licitacao_id: int, question: str, top_k: int = 4) -> List[Tuple[float, str]]:
    """Retorna top_k (score, chunk) mais similares para a pergunta."""
    q_emb = embed_texts([question])[0]
    rows = db.query(EditalEmbedding).filter(EditalEmbedding.licitacao_id == licitacao_id).all()
    scored: List[Tuple[float, str]] = []
    for r in rows:
        try:
            emb = json.loads(r.embedding)
            score = cosine(q_emb, emb)
            scored.append((score, r.content))
        except Exception:
            continue
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]

