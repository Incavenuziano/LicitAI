from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime, timedelta
import json

from pydantic import BaseModel

from src import crud, models, schemas, analysis_service
from src.agents.agente_busca import consultar_licitacoes_publicadas
from src.agents.agente_tratamento import salvar_licitacoes
from src.integrations.anexos import comprasnet_contrato_arquivos, pncp_extrair_anexos_de_pagina
from src.integrations.pncp import listar_documentos_compra, baixar_documento_por_sequencial
from src.integrations.pncp import pncp_buscar_por_link_expanded
from src.integrations.comprasnet import comprasnet_buscar_por_termo
from src.embeddings_service import index_licitacao, query_licitacao
from src.database import get_db, engine
from src.agents.agente_preco_vencedor import pesquisar_precos_vencedores_similares, pesquisar_precos_por_item

try:
    from src.agents.agno_agent import run_agent as run_agno_agent
    HAVE_AGNO = True
except Exception:
    HAVE_AGNO = False

# Cria as tabelas no banco de dados (se não existirem)
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

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

# --- Autenticação e Usuário ---
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/login", response_model=schemas.User)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # normaliza email (trim + lower-case)
    email = (form_data.username or "").strip().lower()
    user = crud.get_user_by_email(db, email=email)
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# --- Licitações ---
@app.get("/licitacoes", response_model=List[schemas.Licitacao])
def read_licitacoes(skip: int = 0, db: Session = Depends(get_db)):
    licitacoes = crud.get_licitacoes(db, skip=skip)
    return licitacoes

# --- Análise de Editais ---
@app.post("/analises/", status_code=status.HTTP_202_ACCEPTED)
def request_analise_de_licitacoes(
    request: schemas.AnaliseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    created_analises = []
    for licitacao_id in request.licitacao_ids:
        db_analise = crud.create_licitacao_analise(db=db, licitacao_id=licitacao_id)
        background_tasks.add_task(analysis_service.run_analysis, analise_id=db_analise.id)
        created_analises.append(db_analise)
    return {"message": f"Análise iniciada para {len(created_analises)} licitações.", "analises": created_analises}

@app.get("/")
def read_root():
    return {"message": "API do LicitAI no ar!"}

@app.get("/health/ocr")
def health_ocr():
    return analysis_service.get_ocr_health()

# --- Buscar e Salvar novas Licitações ---
@app.post("/buscar_licitacoes", status_code=status.HTTP_202_ACCEPTED)
def buscar_licitacoes(request: schemas.BuscaLicitacoesRequest):
    def fmt(d: Optional[date]) -> Optional[str]:
        try:
            return d.strftime("%Y%m%d") if d else None
        except Exception:
            return None

    data_inicial = fmt(request.data_inicio)
    data_final = fmt(request.data_fim)

    raw_json = consultar_licitacoes_publicadas(
        codigo_modalidade=request.codigo_modalidade,
        data_inicial=data_inicial,
        data_final=data_final,
        uf=request.uf,
        tamanho_pagina=request.tamanho_pagina or 10,
    )

    salvar_result = salvar_licitacoes(raw_json)
    try:
        salvar_dict = json.loads(salvar_result)
    except Exception:
        salvar_dict = {"mensagem": salvar_result}

    return {
        "message": "Busca solicitada e dados processados.",
        "params": {
            "codigo_modalidade": request.codigo_modalidade,
            "data_inicio": data_inicial,
            "data_fim": data_final,
            "uf": request.uf,
            "tamanho_pagina": request.tamanho_pagina,
        },
        "resultado": salvar_dict,
    }

# --- Anexos ---
@app.get("/anexos/comprasnet/contrato/{contrato_id}")
def anexos_comprasnet_contrato(contrato_id: int, base_url: Optional[str] = None):
    arquivos = comprasnet_contrato_arquivos(contrato_id=contrato_id, base_url=base_url or 'https://contratos.comprasnet.gov.br')
    return {"contrato_id": contrato_id, "arquivos": arquivos, "count": len(arquivos)}

@app.get("/anexos/pncp")
def anexos_pncp(link: str):
    pdfs = pncp_extrair_anexos_de_pagina(link)
    return {"link": link, "pdfs": pdfs, "count": len(pdfs)}

@app.get("/anexos/licitacao/{licitacao_id}")
def anexos_por_licitacao(licitacao_id: int, db: Session = Depends(get_db)):
    lic = db.query(models.Licitacao).filter(models.Licitacao.id == licitacao_id).first()
    if not lic or not lic.link_sistema_origem:
        raise HTTPException(status_code=404, detail="Licitação não encontrada ou sem link.")

    def map_modalidade(nome: Optional[str]) -> Optional[int]:
        if not nome:
            return None
        nm = (nome or "").lower()
        if "preg" in nm:  # pregão / pregão eletrônico
            return 6
        return None

    pdfs: list[str] = []
    fonte = "fallback"
    page_link_used: Optional[str] = None
    pncp_numero: Optional[str] = None

    try:
        # A busca expandida não precisa do código da modalidade mapeado
        row = pncp_buscar_por_link_expanded(
            link_sistema_origem=lic.link_sistema_origem,
            data_hint=lic.data_publicacao_pncp,
            uf=getattr(lic, "uf", None),
        )
        if isinstance(row, dict):
            pncp_numero = row.get("numeroControlePNCP")
            page_link = row.get("linkProcessoEletronico") or row.get("linkSistemaOrigem") or lic.link_sistema_origem
            page_link_used = page_link
            pdfs = pncp_extrair_anexos_de_pagina(page_link)
            fonte = "pncp_expanded" # Mudei a fonte para sabermos que a nova função foi usada
    except Exception:
        pass

    # Fallback: se a busca por link no PNCP falhou, tenta busca por termo no Comprasnet
    if not pncp_numero and lic.objeto_compra:
        print(f"INFO: PNCP link search failed. Falling back to Comprasnet keyword search for: {lic.objeto_compra[:50]}...")
        try:
            potential_matches = comprasnet_buscar_por_termo(lic.objeto_compra)
            if potential_matches:
                print(f"INFO: Found {len(potential_matches)} potential matches on Comprasnet.")
                
                # TODO: Implementar lógica de pontuação (scoring) para escolher o melhor match
                # Por enquanto, estamos pegando o primeiro resultado como prova de conceito.
                best_match = potential_matches[0]
                
                # Tenta usar os dados do Comprasnet para encontrar os anexos
                # A estrutura do 'best_match' pode precisar de ajustes conforme a API real
                comprasnet_link = best_match.get('link')
                if comprasnet_link:
                    page_link_used = comprasnet_link
                    pdfs = pncp_extrair_anexos_de_pagina(page_link_used)
                    fonte = "comprasnet_keyword"
                    # O resultado do Comprasnet pode ou não ter o número do PNCP
                    pncp_numero = best_match.get('numero_controle_pncp') or pncp_numero

        except Exception as e:
            print(f"WARN: Comprasnet fallback search failed with error: {e}")
            pass

    # fallback: tenta direto no link do sistema de origem
    if not pdfs:
        pdfs = pncp_extrair_anexos_de_pagina(lic.link_sistema_origem)
        page_link_used = page_link_used or lic.link_sistema_origem

    # remove duplicatas
    seen = set()
    uniq = []
    for u in pdfs:
        if u not in seen:
            uniq.append(u)
            seen.add(u)

    return {
        "licitacao_id": licitacao_id,
        "fonte": fonte,
        "page_link": page_link_used,
        "numero_controle_pncp": pncp_numero or getattr(lic, "numero_controle_pncp", None),
        "pdfs": uniq,
        "count": len(uniq),
    }

# --- PNCP: Documentos da compra (debug/uso direto) ---
@app.get("/pncp/compra/{cnpj}/{ano}/{sequencial}/documentos")
def pncp_documentos_compra(cnpj: str, ano: int, sequencial: int):
    docs = listar_documentos_compra(cnpj, ano, sequencial)
    return {"cnpj": cnpj, "ano": ano, "sequencial": sequencial, "documentos": docs, "count": len(docs)}


class PNCPDocDownload(BaseModel):
    licitacao_id: Optional[int] = None


@app.post("/pncp/compra/{cnpj}/{ano}/{sequencial}/documentos/{seq_doc}/download")
def pncp_baixar_documento(cnpj: str, ano: int, sequencial: int, seq_doc: int, body: PNCPDocDownload | None = None, db: Session = Depends(get_db)):
    path = baixar_documento_por_sequencial(cnpj, ano, sequencial, seq_doc)
    if not path:
        raise HTTPException(status_code=404, detail="Documento não encontrado/baixado")
    # opcional: registrar anexo
    try:
        import hashlib
        from pathlib import Path
        p = Path(path)
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        crud.create_anexo(
            db,
            licitacao_id=(body.licitacao_id if body else None),
            source='pncp_docs',
            url=None,
            filename=p.name,
            local_path=str(p),
            content_type='',
            size_bytes=p.stat().st_size,
            sha256=sha,
            score=None,
            status='saved',
            error=None,
        )
    except Exception:
        pass
    return {"saved_path": path}

# --- Agente (Gemini-flash via Agno) ---
class AgentRunRequest(BaseModel):
    prompt: str
    uf: Optional[str] = None
    data_inicio: Optional[str] = None  # YYYY-MM-DD
    data_fim: Optional[str] = None     # YYYY-MM-DD
    codigo_modalidade: Optional[int] = None
    tamanho_pagina: Optional[int] = None

@app.post("/agent/run")
def agent_run(req: AgentRunRequest):
    if not HAVE_AGNO:
        raise HTTPException(
            status_code=501,
            detail="Agno não instalado. Instale com: pip install agno google-generativeai e defina GEMINI_API_KEY.",
        )
    ctx = {}
    if req.uf:
        ctx["uf"] = req.uf
    if req.data_inicio:
        ctx["data_inicio"] = req.data_inicio
    if req.data_fim:
        ctx["data_fim"] = req.data_fim
    if req.codigo_modalidade is not None:
        ctx["codigo_modalidade"] = req.codigo_modalidade
    if req.tamanho_pagina is not None:
        ctx["tamanho_pagina"] = req.tamanho_pagina

    try:
        result = run_agno_agent(req.prompt, context=ctx)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao executar agente: {e}")

# --- RAG: Indexação e Perguntas ao Edital ---
class RagQuestion(BaseModel):
    question: str
    top_k: Optional[int] = 4

@app.post("/rag/indexar/{licitacao_id}")
def rag_indexar(licitacao_id: int, db: Session = Depends(get_db)):
    lic = db.query(models.Licitacao).filter(models.Licitacao.id == licitacao_id).first()
    if not lic or not lic.link_sistema_origem:
        raise HTTPException(status_code=404, detail="Licitação não encontrada ou sem link de edital")

    from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime, timedelta
import json

from pydantic import BaseModel

from src import crud, models, schemas, analysis_service
from src.agents.agente_busca import consultar_licitacoes_publicadas
from src.agents.agente_tratamento import salvar_licitacoes
from src.integrations.anexos import comprasnet_contrato_arquivos, pncp_extrair_anexos_de_pagina
from src.embeddings_service import index_licitacao, query_licitacao
from src.database import get_db, engine
from src.agents.agente_preco_vencedor import pesquisar_precos_vencedores_similares, pesquisar_precos_por_item

try:
    from src.agents.agno_agent import run_agent as run_agno_agent
    HAVE_AGNO = True
except Exception:
    HAVE_AGNO = False

# Cria as tabelas no banco de dados (se não existirem)
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

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

# --- Autenticação e Usuário ---
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/login", response_model=schemas.User)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # normaliza email (trim + lower-case)
    email = (form_data.username or "").strip().lower()
    user = crud.get_user_by_email(db, email=email)
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# --- Licitações ---
@app.get("/licitacoes", response_model=List[schemas.Licitacao])
def read_licitacoes(skip: int = 0, db: Session = Depends(get_db)):
    licitacoes = crud.get_licitacoes(db, skip=skip)
    return licitacoes

# --- Análise de Editais ---
@app.post("/analises/", status_code=status.HTTP_202_ACCEPTED)
def request_analise_de_licitacoes(
    request: schemas.AnaliseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    created_analises = []
    for licitacao_id in request.licitacao_ids:
        db_analise = crud.create_licitacao_analise(db=db, licitacao_id=licitacao_id)
        background_tasks.add_task(analysis_service.run_analysis, analise_id=db_analise.id)
        created_analises.append(db_analise)
    return {"message": f"Análise iniciada para {len(created_analises)} licitações.", "analises": created_analises}

@app.get("/")
def read_root():
    return {"message": "API do LicitAI no ar!"}

@app.get("/health/ocr")
def health_ocr():
    return analysis_service.get_ocr_health()

# --- Buscar e Salvar novas Licitações ---
@app.post("/buscar_licitacoes", status_code=status.HTTP_202_ACCEPTED)
def buscar_licitacoes(request: schemas.BuscaLicitacoesRequest):
    def fmt(d: Optional[date]) -> Optional[str]:
        try:
            return d.strftime("%Y%m%d") if d else None
        except Exception:
            return None

    data_inicial = fmt(request.data_inicio)
    data_final = fmt(request.data_fim)

    raw_json = consultar_licitacoes_publicadas(
        codigo_modalidade=request.codigo_modalidade,
        data_inicial=data_inicial,
        data_final=data_final,
        uf=request.uf,
        tamanho_pagina=request.tamanho_pagina or 10,
    )

    salvar_result = salvar_licitacoes(raw_json)
    try:
        salvar_dict = json.loads(salvar_result)
    except Exception:
        salvar_dict = {"mensagem": salvar_result}

    return {
        "message": "Busca solicitada e dados processados.",
        "params": {
            "codigo_modalidade": request.codigo_modalidade,
            "data_inicio": data_inicial,
            "data_fim": data_final,
            "uf": request.uf,
            "tamanho_pagina": request.tamanho_pagina,
        },
        "resultado": salvar_dict,
    }

# --- Anexos ---
@app.get("/anexos/comprasnet/contrato/{contrato_id}")
def anexos_comprasnet_contrato(contrato_id: int, base_url: Optional[str] = None):
    arquivos = comprasnet_contrato_arquivos(contrato_id=contrato_id, base_url=base_url or 'https://contratos.comprasnet.gov.br')
    return {"contrato_id": contrato_id, "arquivos": arquivos, "count": len(arquivos)}

@app.get("/anexos/pncp")
def anexos_pncp(link: str):
    pdfs = pncp_extrair_anexos_de_pagina(link)
    return {"link": link, "pdfs": pdfs, "count": len(pdfs)}

# --- Agente (Gemini-flash via Agno) ---
class AgentRunRequest(BaseModel):
    prompt: str
    uf: Optional[str] = None
    data_inicio: Optional[str] = None  # YYYY-MM-DD
    data_fim: Optional[str] = None     # YYYY-MM-DD
    codigo_modalidade: Optional[int] = None
    tamanho_pagina: Optional[int] = None

@app.post("/agent/run")
def agent_run(req: AgentRunRequest):
    if not HAVE_AGNO:
        raise HTTPException(
            status_code=501,
            detail="Agno não instalado. Instale com: pip install agno google-generativeai e defina GEMINI_API_KEY.",
        )
    ctx = {}
    if req.uf:
        ctx["uf"] = req.uf
    if req.data_inicio:
        ctx["data_inicio"] = req.data_inicio
    if req.data_fim:
        ctx["data_fim"] = req.data_fim
    if req.codigo_modalidade is not None:
        ctx["codigo_modalidade"] = req.codigo_modalidade
    if req.tamanho_pagina is not None:
        ctx["tamanho_pagina"] = req.tamanho_pagina

    try:
        result = run_agno_agent(req.prompt, context=ctx)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao executar agente: {e}")

# --- RAG: Indexação e Perguntas ao Edital ---
class RagQuestion(BaseModel):
    question: str
    top_k: Optional[int] = 4

@app.post("/rag/indexar/{licitacao_id}")
def rag_indexar(licitacao_id: int, db: Session = Depends(get_db)):
    lic = db.query(models.Licitacao).filter(models.Licitacao.id == licitacao_id).first()
    if not lic or not lic.link_sistema_origem:
        raise HTTPException(status_code=404, detail="Licitação não encontrada ou sem link de edital")

    from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime, timedelta
import json

from pydantic import BaseModel

from src import crud, models, schemas, analysis_service
from src.agents.agente_busca import consultar_licitacoes_publicadas
from src.agents.agente_tratamento import salvar_licitacoes
from src.integrations.anexos import comprasnet_contrato_arquivos, pncp_extrair_anexos_de_pagina
from src.embeddings_service import index_licitacao, query_licitacao
from src.database import get_db, engine
from src.agents.agente_preco_vencedor import pesquisar_precos_vencedores_similares, pesquisar_precos_por_item

try:
    from src.agents.agno_agent import run_agent as run_agno_agent
    HAVE_AGNO = True
except Exception:
    HAVE_AGNO = False

# Cria as tabelas no banco de dados (se não existirem)
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

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

# --- Autenticação e Usuário ---
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/login", response_model=schemas.User)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # normaliza email (trim + lower-case)
    email = (form_data.username or "").strip().lower()
    user = crud.get_user_by_email(db, email=email)
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# --- Licitações ---
@app.get("/licitacoes", response_model=List[schemas.Licitacao])
def read_licitacoes(skip: int = 0, db: Session = Depends(get_db)):
    licitacoes = crud.get_licitacoes(db, skip=skip)
    return licitacoes

# --- Análise de Editais ---
@app.post("/analises/", status_code=status.HTTP_202_ACCEPTED)
def request_analise_de_licitacoes(
    request: schemas.AnaliseRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    created_analises = []
    for licitacao_id in request.licitacao_ids:
        db_analise = crud.create_licitacao_analise(db=db, licitacao_id=licitacao_id)
        background_tasks.add_task(analysis_service.run_analysis, analise_id=db_analise.id)
        created_analises.append(db_analise)
    return {"message": f"Análise iniciada para {len(created_analises)} licitações.", "analises": created_analises}

@app.get("/")
def read_root():
    return {"message": "API do LicitAI no ar!"}

@app.get("/health/ocr")
def health_ocr():
    return analysis_service.get_ocr_health()

# --- Buscar e Salvar novas Licitações ---
@app.post("/buscar_licitacoes", status_code=status.HTTP_202_ACCEPTED)
def buscar_licitacoes(request: schemas.BuscaLicitacoesRequest):
    def fmt(d: Optional[date]) -> Optional[str]:
        try:
            return d.strftime("%Y%m%d") if d else None
        except Exception:
            return None

    data_inicial = fmt(request.data_inicio)
    data_final = fmt(request.data_fim)

    raw_json = consultar_licitacoes_publicadas(
        codigo_modalidade=request.codigo_modalidade,
        data_inicial=data_inicial,
        data_final=data_final,
        uf=request.uf,
        tamanho_pagina=request.tamanho_pagina or 10,
    )

    salvar_result = salvar_licitacoes(raw_json)
    try:
        salvar_dict = json.loads(salvar_result)
    except Exception:
        salvar_dict = {"mensagem": salvar_result}

    return {
        "message": "Busca solicitada e dados processados.",
        "params": {
            "codigo_modalidade": request.codigo_modalidade,
            "data_inicio": data_inicial,
            "data_fim": data_final,
            "uf": request.uf,
            "tamanho_pagina": request.tamanho_pagina,
        },
        "resultado": salvar_dict,
    }

# --- Anexos ---
@app.get("/anexos/comprasnet/contrato/{contrato_id}")
def anexos_comprasnet_contrato(contrato_id: int, base_url: Optional[str] = None):
    arquivos = comprasnet_contrato_arquivos(contrato_id=contrato_id, base_url=base_url or 'https://contratos.comprasnet.gov.br')
    return {"contrato_id": contrato_id, "arquivos": arquivos, "count": len(arquivos)}

@app.get("/anexos/pncp")
def anexos_pncp(link: str):
    pdfs = pncp_extrair_anexos_de_pagina(link)
    return {"link": link, "pdfs": pdfs, "count": len(pdfs)}

# --- Agente (Gemini-flash via Agno) ---
class AgentRunRequest(BaseModel):
    prompt: str
    uf: Optional[str] = None
    data_inicio: Optional[str] = None  # YYYY-MM-DD
    data_fim: Optional[str] = None     # YYYY-MM-DD
    codigo_modalidade: Optional[int] = None
    tamanho_pagina: Optional[int] = None

@app.post("/agent/run")
def agent_run(req: AgentRunRequest):
    if not HAVE_AGNO:
        raise HTTPException(
            status_code=501,
            detail="Agno não instalado. Instale com: pip install agno google-generativeai e defina GEMINI_API_KEY.",
        )
    ctx = {}
    if req.uf:
        ctx["uf"] = req.uf
    if req.data_inicio:
        ctx["data_inicio"] = req.data_inicio
    if req.data_fim:
        ctx["data_fim"] = req.data_fim
    if req.codigo_modalidade is not None:
        ctx["codigo_modalidade"] = req.codigo_modalidade
    if req.tamanho_pagina is not None:
        ctx["tamanho_pagina"] = req.tamanho_pagina

    try:
        result = run_agno_agent(req.prompt, context=ctx)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao executar agente: {e}")

# --- RAG: Indexação e Perguntas ao Edital ---
class RagQuestion(BaseModel):
    question: str
    top_k: Optional[int] = 4

@app.post("/rag/indexar/{licitacao_id}")
def rag_indexar(licitacao_id: int, db: Session = Depends(get_db)):
    lic = db.query(models.Licitacao).filter(models.Licitacao.id == licitacao_id).first()
    if not lic or not lic.link_sistema_origem:
        raise HTTPException(status_code=404, detail="Licitação não encontrada ou sem link de edital")

    from src.analysis_service import extract_text_from_link  # type: ignore

    def extractor(licitacao: models.Licitacao) -> str:
        texto, _meta = extract_text_from_link(licitacao.link_sistema_origem)
        return texto or ""

    count = index_licitacao(db, lic, extractor)
    return {"licitacao_id": licitacao_id, "chunks_indexados": count}

@app.post("/rag/perguntar/{licitacao_id}")
def rag_perguntar(licitacao_id: int, req: RagQuestion, db: Session = Depends(get_db)):
    top = query_licitacao(db, licitacao_id, req.question, top_k=req.top_k or 4)
    return {
        "licitacao_id": licitacao_id,
        "question": req.question,
        "results": [{"score": float(s), "chunk": c} for s, c in top],
    }


# --- Itens do Edital ---
class ItemsRequest(BaseModel):
    link: Optional[str] = None
    licitacao_id: Optional[int] = None


@app.post("/analises/itens")
def extrair_itens(req: ItemsRequest, db: Session = Depends(get_db)):
    link: Optional[str] = (req.link or "").strip() or None
    if not link and req.licitacao_id is not None:
        lic = db.query(models.Licitacao).filter(models.Licitacao.id == req.licitacao_id).first()
        if not lic:
            raise HTTPException(status_code=404, detail="Licitação não encontrada")
        if not lic.link_sistema_origem:
            raise HTTPException(status_code=400, detail="Licitação sem link de edital")
        link = lic.link_sistema_origem
    if not link:
        raise HTTPException(status_code=400, detail="Informe 'link' ou 'licitacao_id'")

    try:
        _texto, meta = analysis_service.extract_text_from_link(link)
        itens = meta.get("itens") or []
        return {"itens": itens, "count": int(meta.get("itens_count") or len(itens))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao extrair itens: {e}")


# --- Agente: Preço vencedor de itens similares ---
class PrecoRequest(BaseModel):
    top_k: Optional[int] = 20

@app.get("/pesquisa/precos_por_item")
async def pesquisar_precos_action(descricao: str, fonte: Optional[str] = "comprasgov", db: Session = Depends(get_db)):
    """Pesquisa preços de um item por sua descrição textual."""
    if not descricao or not descricao.strip():
        raise HTTPException(status_code=400, detail="Descrição não pode ser vazia.")
    result = await pesquisar_precos_por_item(db, descricao=descricao, fonte=(fonte or "comprasgov"))
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    # Add a local count for compatibility with tests
    try:
        count_locais = db.query(models.Licitacao).filter(models.Licitacao.objeto_compra.ilike(f"%{descricao}%")).count()
    except Exception:
        count_locais = 0
    payload = dict(result)
    payload.setdefault("licitacoes_locais_consideradas", count_locais)
    return payload

@app.get("/agentes/preco_vencedor/{licitacao_id}")
async def agente_preco_vencedor(licitacao_id: int, top_k: Optional[int] = 20, fonte: Optional[str] = "comprasgov", db: Session = Depends(get_db)):
    """Pesquisa preços vencedores de itens semelhantes à licitação informada e retorna estatísticas."""
    result = await pesquisar_precos_vencedores_similares(db, licitacao_id, top_k_similares=top_k or 20, fonte=(fonte or "comprasgov"))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


    def extractor(licitacao: models.Licitacao) -> str:
        texto, _meta = extract_text_from_link(licitacao.link_sistema_origem)
        return texto or ""

    count = index_licitacao(db, lic, extractor)
    return {"licitacao_id": licitacao_id, "chunks_indexados": count}

@app.post("/rag/perguntar/{licitacao_id}")
def rag_perguntar(licitacao_id: int, req: RagQuestion, db: Session = Depends(get_db)):
    top = query_licitacao(db, licitacao_id, req.question, top_k=req.top_k or 4)
    return {
        "licitacao_id": licitacao_id,
        "question": req.question,
        "results": [{"score": float(s), "chunk": c} for s, c in top],
    }


# --- Itens do Edital ---
class ItemsRequest(BaseModel):
    link: Optional[str] = None
    licitacao_id: Optional[int] = None


@app.post("/analises/itens")
def extrair_itens(req: ItemsRequest, db: Session = Depends(get_db)):
    link: Optional[str] = (req.link or "").strip() or None
    if not link and req.licitacao_id is not None:
        lic = db.query(models.Licitacao).filter(models.Licitacao.id == req.licitacao_id).first()
        if not lic:
            raise HTTPException(status_code=404, detail="Licitação não encontrada")
        if not lic.link_sistema_origem:
            raise HTTPException(status_code=400, detail="Licitação sem link de edital")
        link = lic.link_sistema_origem
    if not link:
        raise HTTPException(status_code=400, detail="Informe 'link' ou 'licitacao_id'")

    try:
        _texto, meta = analysis_service.extract_text_from_link(link)
        itens = meta.get("itens") or []
        return {"itens": itens, "count": int(meta.get("itens_count") or len(itens))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao extrair itens: {e}")


# --- Agente: Preço vencedor de itens similares ---
class PrecoRequest(BaseModel):
    top_k: Optional[int] = 20

@app.get("/pesquisa/precos_por_item")
async def pesquisar_precos_action(descricao: str, fonte: Optional[str] = "comprasgov", db: Session = Depends(get_db)):
    """Pesquisa preços de um item por sua descrição textual."""
    if not descricao or not descricao.strip():
        raise HTTPException(status_code=400, detail="Descrição não pode ser vazia.")
    result = await pesquisar_precos_por_item(db, descricao=descricao, fonte=(fonte or "comprasgov"))
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    # Add a local count for compatibility with tests
    try:
        count_locais = db.query(models.Licitacao).filter(models.Licitacao.objeto_compra.ilike(f"%{descricao}%")).count()
    except Exception:
        count_locais = 0
    payload = dict(result)
    payload.setdefault("licitacoes_locais_consideradas", count_locais)
    return payload

@app.get("/agentes/preco_vencedor/{licitacao_id}")
async def agente_preco_vencedor(licitacao_id: int, top_k: Optional[int] = 20, fonte: Optional[str] = "comprasgov", db: Session = Depends(get_db)):
    """Pesquisa preços vencedores de itens semelhantes à licitação informada e retorna estatísticas."""
    result = await pesquisar_precos_vencedores_similares(db, licitacao_id, top_k_similares=top_k or 20, fonte=(fonte or "comprasgov"))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


    def extractor(licitacao: models.Licitacao) -> str:
        texto, _meta = extract_text_from_link(licitacao.link_sistema_origem)
        return texto or ""

    count = index_licitacao(db, lic, extractor)
    return {"licitacao_id": licitacao_id, "chunks_indexados": count}

@app.post("/rag/perguntar/{licitacao_id}")
def rag_perguntar(licitacao_id: int, req: RagQuestion, db: Session = Depends(get_db)):
    top = query_licitacao(db, licitacao_id, req.question, top_k=req.top_k or 4)
    return {
        "licitacao_id": licitacao_id,
        "question": req.question,
        "results": [{"score": float(s), "chunk": c} for s, c in top],
    }


# --- Itens do Edital ---
class ItemsRequest(BaseModel):
    link: Optional[str] = None
    licitacao_id: Optional[int] = None


@app.post("/analises/itens")
def extrair_itens(req: ItemsRequest, db: Session = Depends(get_db)):
    link: Optional[str] = (req.link or "").strip() or None
    if not link and req.licitacao_id is not None:
        lic = db.query(models.Licitacao).filter(models.Licitacao.id == req.licitacao_id).first()
        if not lic:
            raise HTTPException(status_code=404, detail="Licitação não encontrada")
        if not lic.link_sistema_origem:
            raise HTTPException(status_code=400, detail="Licitação sem link de edital")
        link = lic.link_sistema_origem
    if not link:
        raise HTTPException(status_code=400, detail="Informe 'link' ou 'licitacao_id'")

    try:
        _texto, meta = analysis_service.extract_text_from_link(link)
        itens = meta.get("itens") or []
        return {"itens": itens, "count": int(meta.get("itens_count") or len(itens))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falha ao extrair itens: {e}")


# --- Agente: Preço vencedor de itens similares ---
class PrecoRequest(BaseModel):
    top_k: Optional[int] = 20

@app.get("/pesquisa/precos_por_item")
async def pesquisar_precos_action(descricao: str, fonte: Optional[str] = "comprasgov", db: Session = Depends(get_db)):
    """Pesquisa preços de um item por sua descrição textual."""
    if not descricao or not descricao.strip():
        raise HTTPException(status_code=400, detail="Descrição não pode ser vazia.")
    result = await pesquisar_precos_por_item(db, descricao=descricao, fonte=(fonte or "comprasgov"))
    if result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    # Add a local count for compatibility with tests
    try:
        count_locais = db.query(models.Licitacao).filter(models.Licitacao.objeto_compra.ilike(f"%{descricao}%")).count()
    except Exception:
        count_locais = 0
    payload = dict(result)
    payload.setdefault("licitacoes_locais_consideradas", count_locais)
    return payload

@app.get("/agentes/preco_vencedor/{licitacao_id}")
async def agente_preco_vencedor(licitacao_id: int, top_k: Optional[int] = 20, fonte: Optional[str] = "comprasgov", db: Session = Depends(get_db)):
    """Pesquisa preços vencedores de itens semelhantes à licitação informada e retorna estatísticas."""
    result = await pesquisar_precos_vencedores_similares(db, licitacao_id, top_k_similares=top_k or 20, fonte=(fonte or "comprasgov"))
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
