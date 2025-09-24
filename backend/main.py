from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from fastapi import UploadFile, File, Form
from pathlib import Path
import time
import hashlib
import logging
import sys

try:
    # ExecuÃ§Ã£o a partir de backend/
    from src import crud, models, schemas, analysis_service  # type: ignore
    from src.agents.agente_busca import consultar_licitacoes_publicadas  # type: ignore
    from src.agents.agente_busca import (
        consultar_oportunidades_ativas,  # type: ignore
        buscar_oportunidades_ativas_amplo,  # type: ignore
        descobrir_modalidades_publicacao,  # type: ignore
    )
    from src.agents.agente_tratamento import salvar_licitacoes  # type: ignore
    from src.embeddings_service import index_licitacao, query_licitacao  # type: ignore
    from src.agents.agente_preco_vencedor import (  # type: ignore
        pesquisar_precos_por_item as _pesquisar_precos_por_item,
    )
    from src.database import get_db, engine  # type: ignore
    # TransparÃªncia (opcional)
    try:
        from src.integrations.transparencia import pagamentos_por_cnpj  # type: ignore
    except Exception:  # pragma: no cover
        pagamentos_por_cnpj = None  # type: ignore
except ModuleNotFoundError:
    # ExecuÃ§Ã£o/import como pacote 'backend.*'
    from backend.src import crud, models, schemas, analysis_service  # type: ignore
    from backend.src.agents.agente_busca import consultar_licitacoes_publicadas  # type: ignore
    from backend.src.agents.agente_busca import (  # type: ignore
        consultar_oportunidades_ativas,
        buscar_oportunidades_ativas_amplo,
        descobrir_modalidades_publicacao,
    )
    from backend.src.agents.agente_tratamento import salvar_licitacoes  # type: ignore
    from backend.src.embeddings_service import index_licitacao, query_licitacao  # type: ignore
    from backend.src.agents.agente_preco_vencedor import (  # type: ignore
        pesquisar_precos_por_item as _pesquisar_precos_por_item,
    )
    from backend.src.database import get_db, engine  # type: ignore
    try:
        from backend.src.integrations.transparencia import pagamentos_por_cnpj  # type: ignore
    except Exception:  # pragma: no cover
        pagamentos_por_cnpj = None  # type: ignore

# ForÃ§a stdout/stderr para UTF-8 em ambientes Windows/PowerShell
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# Create tables (idempotent)
try:
    models.Base.metadata.create_all(bind=engine)
except Exception:
    # Evita falha no import quando DB nÃ£o estÃ¡ disponÃ­vel
    pass

app = FastAPI()

logger = logging.getLogger("api")

# CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth (minimal)
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/login", response_model=schemas.User)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = (form_data.username or "").strip().lower()
    user = crud.get_user_by_email(db, email=email)
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return user

# Licitacoes
@app.get("/licitacoes", response_model=List[schemas.Licitacao])
def read_licitacoes(
    skip: int = 0,
    limit: int = 100,
    q: Optional[str] = None,
    uf: Optional[str] = None,
    has_analise: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    return crud.get_licitacoes(db, skip=skip, limit=limit, q=q, uf=uf, has_analise=has_analise)

@app.get("/licitacoes/{licitacao_id}", response_model=schemas.Licitacao)
def read_licitacao(licitacao_id: int, db: Session = Depends(get_db)):
    db_licitacao = crud.get_licitacao(db, licitacao_id=licitacao_id)
    if db_licitacao is None:
        raise HTTPException(status_code=404, detail="Licitacao nao encontrada")
    return db_licitacao

# EstatÃ­sticas
@app.get("/stats/licitacoes-por-uf", response_model=list[schemas.StatsUF])
def stats_licitacoes_por_uf(db: Session = Depends(get_db)):
    rows = crud.get_licitacao_count_by_uf(db)
    # rows sÃ£o tuplas (uf, total) ou objetos com atributos; normalizar saÃ­da
    result: list[schemas.StatsUF] = []
    for r in rows:
        try:
            uf = r.uf  # type: ignore[attr-defined]
            total = int(r.total)  # type: ignore[attr-defined]
        except Exception:
            uf, total = r[0], int(r[1])  # fallback se vier como tupla
        result.append(schemas.StatsUF(uf=uf, total=total))
    return result

@app.get("/stats/analises")
def stats_total_analises(db: Session = Depends(get_db)):
    total = crud.get_total_analises(db)
    return {"total": total}


# Analises
class AnaliseRequest(BaseModel):
    licitacao_ids: List[int]

@app.post("/analises/", status_code=status.HTTP_202_ACCEPTED)
def request_analise_de_licitacoes(request: AnaliseRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    logger.info(f"[analises] solicitacao recebida para {len(request.licitacao_ids)} licitacao(oes)")
    created = []
    for licitacao_id in request.licitacao_ids:
        db_analise = crud.create_licitacao_analise(db=db, licitacao_id=licitacao_id)
        logger.info(f"[analises] analise criada id={db_analise.id} licitacao_id={licitacao_id}; agendando background task")
        background_tasks.add_task(analysis_service.run_analysis, analise_id=db_analise.id)
        created.append(db_analise)
    logger.info(f"[analises] agendamento concluido para {len(created)} analise(s)")
    return {"message": f"Analises iniciadas: {len(created)}", "analises": created}

@app.get("/")
def read_root():
    return {"message": "API LicitAI online"}


# Buscar licitaÃ§Ãµes via PNCP e salvar no banco
@app.post("/buscar_licitacoes")
def buscar_licitacoes_endpoint(payload: schemas.BuscaLicitacoesRequest):
    """Consulta licitaÃ§Ãµes no PNCP conforme filtros e salva no banco.

    Retorna um resumo da operaÃ§Ã£o conforme `salvar_licitacoes`.
    """
    # Mapear campos do schema para os parÃ¢metros esperados pelo agente de busca
    json_str = consultar_licitacoes_publicadas(
        codigo_modalidade=payload.codigo_modalidade,
        data_inicial=(payload.data_inicio.isoformat() if payload.data_inicio else None),
        data_final=(payload.data_fim.isoformat() if payload.data_fim else None),
        uf=payload.uf,
        tamanho_pagina=payload.tamanho_pagina or 10,
    )
    resumo_str = salvar_licitacoes(json_str)
    try:
        import json as _json
        return _json.loads(resumo_str)
    except Exception:
        return {"resultado": resumo_str}


# ------- RAG (Embeddings) -------
class RagQuery(BaseModel):
    question: str
    top_k: int = 4


@app.post("/rag/indexar/{licitacao_id}")
def rag_indexar(licitacao_id: int, db: Session = Depends(get_db)):
    """Extrai texto do edital principal e indexa em embeddings."""
    lic = crud.get_licitacao(db, licitacao_id)
    if not lic:
        raise HTTPException(status_code=404, detail="Licitacao nao encontrada")

    from pathlib import Path as _Path
    import os as _os

    def _text_extractor(_lic: models.Licitacao) -> str:
        an = crud.get_principal_anexo(db, _lic.id)
        if not an or not an.local_path or (not _os.path.exists(an.local_path)):
            return ""
        data = _Path(an.local_path).read_bytes()
        txt = analysis_service._extract_text_from_pdf(data) or ""
        if not txt or len(txt) < 100:
            txt = analysis_service._ocr_pdf(data) or ""
        return txt

    try:
        count = index_licitacao(db, lic, _text_extractor)
        return {"indexed_chunks": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao indexar: {e}")


@app.post("/rag/perguntar/{licitacao_id}")
def rag_perguntar(licitacao_id: int, body: RagQuery, db: Session = Depends(get_db)):
    """Consulta os chunks mais relevantes para a pergunta enviada."""
    try:
        results = query_licitacao(db, licitacao_id, body.question, body.top_k)
        return {"results": [{"score": float(s), "chunk": c} for s, c in results]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha na consulta: {e}")


# ------- Pesquisa de PreÃ§os por Item (ComprasGov/PNCP) -------
@app.get("/pesquisa/precos_por_item")
async def pesquisa_precos_por_item(
    descricao: str,
    limit_ids: int = 30,
    fonte: str = "ambas",
    db: Session = Depends(get_db),
):
    """Pesquisa preÃ§os por descriÃ§Ã£o de item consultando fontes pÃºblicas.

    - fonte: "comprasgov" | "pncp" | "ambas"
    - limit_ids: limite de IDs de contratos a considerar (fonte comprasgov)
    """
    try:
        result = await _pesquisar_precos_por_item(db, descricao, limit_ids=limit_ids, fonte=fonte)
        # Compatibilidade com testes existentes: expor campo agregado
        considerados = result.get("considerados", {}) if isinstance(result, dict) else {}
        lic_locais = considerados.get("pncp_licitacoes") if isinstance(considerados, dict) else None
        if isinstance(result, dict):
            out = dict(result)
            if lic_locais is not None:
                out["licitacoes_locais_consideradas"] = lic_locais
            return out
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha na pesquisa de precos: {e}")


@app.get("/licitacoes/{licitacao_id}/precos_vencedores")
async def licitacao_precos_vencedores(
    licitacao_id: int,
    fonte: str = "comprasgov",
    top_k: int = 20,
    db: Session = Depends(get_db),
):
    try:
        try:
            from src.agents.agente_preco_vencedor import pesquisar_precos_vencedores_similares  # type: ignore
        except ModuleNotFoundError:
            from backend.src.agents.agente_preco_vencedor import pesquisar_precos_vencedores_similares  # type: ignore
        result = await pesquisar_precos_vencedores_similares(
            db, licitacao_id, top_k_similares=top_k, fonte=fonte
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao obter precos vencedores: {e}")


# ------- Oportunidades Ativas (PNCP - propostas em aberto) -------
class OportunidadesPayload(BaseModel):
    # modo de varredura
    amplo: bool = False
    # filtros simples
    uf: Optional[str] = None
    data_inicio: Optional[str] = None  # YYYY-MM-DD
    data_fim: Optional[str] = None     # YYYY-MM-DD
    codigo_modalidade: Optional[int] = None
    pagina: int = 1
    tamanho_pagina: int = 50
    salvar: bool = False
    # varredura ampla
    total_days: int = 14
    step_days: int = 7
    ufs: Optional[list[str]] = None
    modal_codes: Optional[list[int]] = None
    page_limit: int = 50
    data_fim_ref: Optional[str] = None  # YYYY-MM-DD


@app.post("/oportunidades/ativas")
def oportunidades_ativas(payload: OportunidadesPayload):
    """Consulta propostas em aberto no PNCP (modo simples ou varredura ampla)."""
    try:
        import json as _json
        if payload.amplo:
            s = buscar_oportunidades_ativas_amplo(
                total_days=payload.total_days,
                step_days=payload.step_days,
                ufs=payload.ufs,
                modal_codes=payload.modal_codes,
                page_limit=payload.page_limit,
                tamanho_pagina=payload.tamanho_pagina,
                data_fim_ref=payload.data_fim_ref,
            )
        else:
            s = consultar_oportunidades_ativas(
                codigo_modalidade=payload.codigo_modalidade,
                data_inicial=payload.data_inicio,
                data_final=payload.data_fim,
                uf=payload.uf,
                pagina=payload.pagina,
                tamanho_pagina=payload.tamanho_pagina,
            )

        try:
            parsed = _json.loads(s)
        except Exception:
            parsed = {"result": s}

        resumo_salvamento = None
        if payload.salvar:
            rows: list[dict] = []
            if isinstance(parsed, dict):
                data_block = parsed.get("data")
                if isinstance(data_block, list):
                    rows = [row for row in data_block if isinstance(row, dict)]
            elif isinstance(parsed, list):
                rows = [row for row in parsed if isinstance(row, dict)]

            if rows:
                try:
                    resumo_salvamento = _json.loads(salvar_licitacoes(_json.dumps(rows, ensure_ascii=False)))
                except Exception as exc:
                    resumo_salvamento = {"status": "erro", "mensagem": f"Falha ao salvar licitacoes: {exc}"}
            else:
                resumo_salvamento = {"status": "info", "mensagem": "Nenhuma licitacao elegivel para salvar."}

            if resumo_salvamento is not None:
                if isinstance(parsed, dict):
                    enriched = dict(parsed)
                    enriched["salvamento"] = resumo_salvamento
                    return enriched
                return {"data": parsed, "salvamento": resumo_salvamento}

        return parsed
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha na consulta de oportunidades: {e}")


@app.post("/licitacoes/salvar")
def salvar_licitacoes_direct(payload: list[dict] | dict):
    """Salva licitaÃ§Ãµes a partir de um payload JSON (lista ou envelope com data).

    CompatÃ­vel com a estrutura retornada pelo PNCP (tanto publicaÃ§Ãµes quanto propostas).
    """
    import json as _json
    try:
        data: list[dict]
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            data = [x for x in payload.get("data", []) if isinstance(x, dict)]  # type: ignore[list-item]
        elif isinstance(payload, list):
            data = [x for x in payload if isinstance(x, dict)]
        else:
            raise ValueError("Payload invÃ¡lido: esperado lista ou objeto com chave 'data'.")

        resumo_str = salvar_licitacoes(_json.dumps(data, ensure_ascii=False))
        try:
            return _json.loads(resumo_str)
        except Exception:
            return {"resultado": resumo_str}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Falha ao salvar licitaÃ§Ãµes: {e}")


# ------- Modalidades (descoberta dinÃ¢mica via PNCP) -------
@app.get("/pncp/modalidades")
def pncp_modalidades():
    try:
        items = descobrir_modalidades_publicacao()
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao descobrir modalidades: {e}")


# ------- SÃ©rie histÃ³rica de preÃ§os -------
class SeriePrecosPayload(BaseModel):
    descricao: Optional[str] = None  # para buscas por objeto (comprasgov/pncp)
    cnpj: Optional[str] = None       # para pagamentos (TransparÃªncia)
    fonte: Optional[str] = None      # 'transparencia' | 'comprasgov' | 'pncp' | 'todas'
    data_inicio: Optional[str] = None  # YYYY-MM-DD
    data_fim: Optional[str] = None     # YYYY-MM-DD


@app.post("/precos/serie")
async def precos_serie(payload: SeriePrecosPayload, db: Session = Depends(get_db)):
    """Retorna sÃ©rie histÃ³rica (date,value,fonte) de preÃ§os/praticados.

    Modos:
      - Se cnpj informado e 'transparencia' disponÃ­vel: usa Portal da TransparÃªncia (despesas/pagamentos).
      - Caso contrÃ¡rio, tenta resumo por descriÃ§Ã£o via fontes pÃºblicas (sem data precisa) e retorna apenas stats.
    """
    try:
        serie: list[dict] = []
        stats = {"count": 0, "min": None, "max": None, "mean": None}
        fonte = (payload.fonte or "transparencia").lower()

        def _upd_stats(values: list[float]):
            if not values:
                return
            import math
            stats["count"] = len(values)
            stats["min"] = float(min(values))
            stats["max"] = float(max(values))
            stats["mean"] = float(sum(values) / len(values))

        # Preferencial: CNPJ + TransparÃªncia (tem datas confiÃ¡veis)
        if payload.cnpj and (fonte in ("transparencia", "todas")):
            if pagamentos_por_cnpj is None:
                raise HTTPException(status_code=501, detail="IntegraÃ§Ã£o com Portal da TransparÃªncia indisponÃ­vel")
            rows = pagamentos_por_cnpj(
                payload.cnpj,
                data_inicio=payload.data_inicio,
                data_fim=payload.data_fim,
                max_paginas=10,
            )
            values: list[float] = []
            for r in rows:
                # heurÃ­stica de campos
                dt = None
                val = None
                try:
                    # tenta chaves usuais
                    for k, v in r.items():
                        kl = str(k).lower()
                        if val is None and isinstance(v, (int, float)) and any(t in kl for t in ["valor", "pago", "liquido", "empenho"]):
                            val = float(v)
                        if dt is None and isinstance(v, str) and "data" in kl:
                            dt = v
                    # normaliza data -> YYYY-MM-DD
                    date_str = None
                    if dt:
                        from datetime import datetime as _dt
                        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%d/%m/%Y %H:%M:%S"):
                            try:
                                date_str = _dt.strptime(dt[:19], fmt).strftime("%Y-%m-%d")
                                break
                            except Exception:
                                continue
                    if val is not None and date_str:
                        values.append(val)
                        serie.append({"date": date_str, "value": val, "fonte": "transparencia"})
                except Exception:
                    continue
            # ordenar
            serie.sort(key=lambda x: x.get("date") or "")
            _upd_stats(values)
            return {"mode": "cnpj/transparencia", "series": serie, "stats": stats}

        # DescriÃ§Ã£o via ComprasGov (com datas de assinatura)
        if payload.descricao and (fonte in ("comprasgov", "todas")):
            try:
                from src.agents.agente_preco_vencedor import serie_comprasgov_por_descricao  # type: ignore
            except ModuleNotFoundError:
                from backend.src.agents.agente_preco_vencedor import serie_comprasgov_por_descricao  # type: ignore
            points = await serie_comprasgov_por_descricao(payload.descricao, limit_ids=30)
            # normaliza e calcula stats
            values = [float(p.get("value")) for p in points if isinstance(p.get("value"), (int, float))]
            values = [v for v in values if v is not None]
            def _s(vs):
                if not vs:
                    return {"count": 0, "min": None, "max": None, "mean": None}
                import math
                return {
                    "count": len(vs),
                    "min": float(min(vs)),
                    "max": float(max(vs)),
                    "mean": float(sum(vs)/len(vs)),
                }
            if fonte == "comprasgov":
                return {"mode": "descricao/comprasgov", "series": points, "stats": _s(values)}
            # fonte == 'todas' â†’ complementar com PNCP
            try:
                from src.agents.agente_preco_vencedor import serie_pncp_por_descricao  # type: ignore
            except ModuleNotFoundError:
                from backend.src.agents.agente_preco_vencedor import serie_pncp_por_descricao  # type: ignore
            pts_pncp = await serie_pncp_por_descricao(payload.descricao)
            combo = points + pts_pncp
            vals = [float(p.get("value")) for p in combo if isinstance(p.get("value"), (int, float))]
            return {
                "mode": "descricao/todas",
                "series": combo,
                "stats": _s(vals),
            }

        # DescriÃ§Ã£o via PNCP (datas de encerramento/publicaÃ§Ã£o)
        if payload.descricao and fonte == "pncp":
            try:
                from src.agents.agente_preco_vencedor import serie_pncp_por_descricao  # type: ignore
            except ModuleNotFoundError:
                from backend.src.agents.agente_preco_vencedor import serie_pncp_por_descricao  # type: ignore
            pts = await serie_pncp_por_descricao(payload.descricao)
            vals = [float(p.get("value")) for p in pts if isinstance(p.get("value"), (int, float))]
            def _s2(vs):
                if not vs:
                    return {"count": 0, "min": None, "max": None, "mean": None}
                import math
                return {
                    "count": len(vs),
                    "min": float(min(vs)),
                    "max": float(max(vs)),
                    "mean": float(sum(vs)/len(vs)),
                }
            return {"mode": "descricao/pncp", "series": pts, "stats": _s2(vals)}

        raise HTTPException(status_code=400, detail="Informe 'cnpj' (preferencial) ou 'descricao'.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao obter sÃ©rie de preÃ§os: {e}")


# ------- DocBox: upload e associaÃ§Ã£o a licitaÃ§Ã£o -------
@app.get("/docbox/{licitacao_id}")
def docbox_list(licitacao_id: int, db: Session = Depends(get_db)):
    try:
        rows = (
            db.query(models.Anexo)
            .filter(models.Anexo.licitacao_id == licitacao_id, models.Anexo.source == 'docbox')
            .order_by(models.Anexo.created_at.desc())
            .all()
        )
        out = []
        for a in rows:
            out.append({
                "id": a.id,
                "filename": a.filename,
                "content_type": a.content_type,
                "size_bytes": a.size_bytes,
                "sha256": a.sha256,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "meta": a.url,  # usamos url para armazenar metadados simples (tag/desc)
            })
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao listar DocBox: {e}")


@app.post("/docbox/upload")
def docbox_upload(
    licitacao_id: int = Form(...),
    file: UploadFile = File(...),
    tag: Optional[str] = Form(None),
    desc: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # pasta de armazenamento
    base_dir = Path(__file__).resolve().parent / "storage" / "docbox" / str(licitacao_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    original = (file.filename or 'arquivo').replace(" ", "_")
    safe_name = f"{ts}_{original}"
    dest = base_dir / safe_name
    data = file.file.read()
    with dest.open("wb") as f:
        f.write(data)
    size_bytes = len(data)
    sha256 = hashlib.sha256(data).hexdigest()
    content_type = file.content_type or 'application/octet-stream'

    # metadados simples no campo url (evita alterar schema): "tag=...;desc=..."
    meta_parts = []
    if tag:
        meta_parts.append(f"tag={tag}")
    if desc:
        meta_parts.append(f"desc={desc}")
    meta_str = ";".join(meta_parts) if meta_parts else None

    anexo = crud.create_anexo(
        db,
        licitacao_id=licitacao_id,
        source='docbox',
        filename=original,
        local_path=str(dest),
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        status='saved',
        url=meta_str,
    )
    return {
        "id": anexo.id,
        "filename": anexo.filename,
        "size_bytes": anexo.size_bytes,
        "sha256": anexo.sha256,
        "created_at": anexo.created_at.isoformat() if anexo.created_at else None,
        "meta": meta_str,
    }


@app.delete("/docbox/{anexo_id}")
def docbox_delete(anexo_id: int, db: Session = Depends(get_db)):
    try:
        a = db.query(models.Anexo).filter(models.Anexo.id == anexo_id, models.Anexo.source == 'docbox').first()
        if not a:
            raise HTTPException(status_code=404, detail="Documento nÃ£o encontrado")
        # apaga arquivo
        try:
            if a.local_path and Path(a.local_path).exists():
                Path(a.local_path).unlink()
        except Exception:
            pass
        db.delete(a)
        db.commit()
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao remover documento: {e}")

# Upload de edital manual
@app.post("/upload/edital/")
def upload_edital(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    orgao_entidade_nome: Optional[str] = Form(None),
    objeto_compra: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # Armazena os uploads dentro do diretÃ³rio da aplicaÃ§Ã£o (/app/tmp/uploads)
    uploads_dir = Path(__file__).resolve().parent / "tmp" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # LÃª e salva arquivo, computa metadados
    ts = int(time.time())
    original = (file.filename or 'arquivo').replace(" ", "_")
    safe_name = f"edital_{ts}_{original}"
    dest = uploads_dir / safe_name
    data = file.file.read()
    with dest.open("wb") as f:
        f.write(data)
    size_bytes = len(data)
    sha256 = hashlib.sha256(data).hexdigest()
    content_type = file.content_type or 'application/octet-stream'

    # Cria licitaÃ§Ã£o mÃ­nima para referenciar a anÃ¡lise
    numero = f"MANUAL-{ts}"
    lic = crud.create_licitacao_manual(
        db,
        numero_controle_pncp=numero,
        objeto_compra=objeto_compra or "Upload manual de edital",
        orgao_entidade_nome=orgao_entidade_nome,
    )

    logger.info(f"[upload] arquivo salvo em {dest} (sha256={sha256}, size={size_bytes}); licitacao criada id={lic.id}")
    analise = crud.create_licitacao_analise(db, licitacao_id=lic.id)

    # Registra anexo associado
    anexo = crud.create_anexo(
        db,
        licitacao_id=lic.id,
        source='direct',
        filename=original,
        local_path=str(dest),
        content_type=content_type,
        size_bytes=size_bytes,
        sha256=sha256,
        status='saved',
    )

    # Tenta extrair metadados bÃ¡sicos do PDF para preencher campos na listagem "No Banco"
    try:
        texto_tmp = analysis_service._extract_text_from_pdf(data) or ""
        if (not texto_tmp) or len(texto_tmp) < 100:
            texto_tmp = analysis_service._ocr_pdf(data) or ""
        if texto_tmp:
            meta = getattr(analysis_service, "_extract_basic_metadata", lambda t: {}) (texto_tmp)
            if isinstance(meta, dict) and meta:
                crud.update_licitacao_fields_if_empty(
                    db,
                    lic.id,
                    objeto_compra=meta.get("objeto_compra"),
                    orgao_entidade_nome=meta.get("orgao_entidade_nome"),
                    data_encerramento_proposta=meta.get("data_encerramento_proposta"),
                )
    except Exception:
        pass

    # Agenda processamento com o arquivo local
    logger.info(f"[upload] analise criada id={analise.id}; anexo id={anexo.id}; agendando background task para processamento do arquivo")
    background_tasks.add_task(
        analysis_service.run_analysis_from_file, analise_id=analise.id, file_path=str(dest)
    )

    return {
        "filename": safe_name,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "analise_id": analise.id,
        "licitacao_id": lic.id,
        "anexo_id": anexo.id,
    }


# RemoÃ§Ã£o de anexos de uma licitaÃ§Ã£o (e arquivo fÃ­sico)
@app.delete("/licitacoes/{licitacao_id}/anexos")
def delete_anexos(licitacao_id: int, db: Session = Depends(get_db)):
    lic = crud.get_licitacao(db, licitacao_id)
    if lic is None:
        raise HTTPException(status_code=404, detail="Licitacao nao encontrada")
    try:
        # Contabiliza anexos antes de apagar para informar na resposta
        pre_count = db.query(models.Anexo).filter(models.Anexo.licitacao_id == licitacao_id).count()
    except Exception:
        pre_count = None

    removed = crud.delete_licitacao_completa(db, licitacao_id)
    return {
        "deleted_anexos": pre_count,
        "licitacao_deleted": bool(removed),
    }

