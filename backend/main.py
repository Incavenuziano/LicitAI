from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from src import crud, models, schemas, analysis_service
from src.database import get_db, engine

# Cria as tabelas no banco de dados (se não existirem)
# A nova tabela 'analises' será criada aqui ao reiniciar o servidor
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Configuração do CORS
origins = [
    "http://localhost:3000",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Endpoints de Autenticação e Usuário ---
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


# --- Endpoint de Licitações ---
@app.get("/licitacoes", response_model=List[schemas.Licitacao])
def read_licitacoes(skip: int = 0, db: Session = Depends(get_db)):
    licitacoes = crud.get_licitacoes(db, skip=skip)
    return licitacoes


# --- Endpoint de Análise de Editais ---
@app.post("/analises/", status_code=status.HTTP_202_ACCEPTED)
def request_analise_de_licitacoes(
    request: schemas.AnaliseRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    created_analises = []
    for licitacao_id in request.licitacao_ids:
        # Cria ou reseta a análise para o status "Pendente"
        db_analise = crud.create_licitacao_analise(db=db, licitacao_id=licitacao_id)
        
        # Adiciona a tarefa de análise em segundo plano
        background_tasks.add_task(analysis_service.run_analysis, db=db, analise_id=db_analise.id)
        
        created_analises.append(db_analise)
        
    return {"message": f"Análise iniciada para {len(created_analises)} licitações.", "analises": created_analises}


@app.get("/")
def read_root():
    return {"message": "API do LicitAI no ar!"}