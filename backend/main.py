from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from src import crud, models, schemas, analysis_service
from src.database import get_db, engine

# Create tables (idempotent)
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
def read_licitacoes(skip: int = 0, limit: int = 100, q: Optional[str] = None, uf: Optional[str] = None, db: Session = Depends(get_db)):
    return crud.get_licitacoes(db, skip=skip, limit=limit, q=q, uf=uf)

@app.get("/licitacoes/{licitacao_id}", response_model=schemas.Licitacao)
def read_licitacao(licitacao_id: int, db: Session = Depends(get_db)):
    db_licitacao = crud.get_licitacao(db, licitacao_id=licitacao_id)
    if db_licitacao is None:
        raise HTTPException(status_code=404, detail="Licitacao nao encontrada")
    return db_licitacao

# Analises
class AnaliseRequest(BaseModel):
    licitacao_ids: List[int]

@app.post("/analises/", status_code=status.HTTP_202_ACCEPTED)
def request_analise_de_licitacoes(request: AnaliseRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    created = []
    for licitacao_id in request.licitacao_ids:
        db_analise = crud.create_licitacao_analise(db=db, licitacao_id=licitacao_id)
        background_tasks.add_task(analysis_service.run_analysis, analise_id=db_analise.id)
        created.append(db_analise)
    return {"message": f"Analises iniciadas: {len(created)}", "analises": created}

@app.get("/")
def read_root():
    return {"message": "API LicitAI online"}
