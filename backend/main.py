from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

from src import crud, models, schemas
from src.database import get_db, engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Configuração do CORS
origins = [
    "http://localhost:3000",  # Endereço do nosso frontend Next.js
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos (GET, POST, etc)
    allow_headers=["*"],  # Permite todos os cabeçalhos
)


# --- Endpoint de Criação de Usuário (CORRIGIDO) ---
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)


# --- Endpoint de Login (NOVO) ---
@app.post("/login", response_model=schemas.User)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # O campo 'username' do formulário OAuth2 é usado para o email
    user = crud.get_user_by_email(db, email=form_data.username)
    
    if not user or not crud.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


@app.get("/licitacoes", response_model=List[schemas.Licitacao])
def read_licitacoes(skip: int = 0, db: Session = Depends(get_db)):
    licitacoes = crud.get_licitacoes(db, skip=skip)
    return licitacoes


@app.get("/")
def read_root():
    return {"message": "API do LicitAI no ar!"}
