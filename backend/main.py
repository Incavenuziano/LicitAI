from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
import json

from pydantic import BaseModel

from src import crud, models, schemas, analysis_service
from src.agents.agente_busca import consultar_licitacoes_publicadas
from src.agents.agente_tratamento import salvar_licitacoes
from src.integrations.anexos import comprasnet_contrato_arquivos, pncp_extrair_anexos_de_pagina
from src.embeddings_service import index_licitacao, query_licitacao
from src.database import get_db, engine

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
    user = crud.get_user_by_email(db, email=form_data.username)
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
