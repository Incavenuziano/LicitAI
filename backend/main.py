from fastapi import FastAPI

# Importa nossos módulos de banco de dados e modelos                                                                               │      
from . import models                                                                                                               │      
from .database import engine                                                                                                       │      
                                                                                                                                    │      
# Esta linha instrui o SQLAlchemy a criar todas as tabelas (neste caso, apenas a tabela 'users')                                   │      
# que ele encontrar nos modelos que herdam da nossa classe Base.                                                                   │      
models.Base.metadata.create_all(bind=engine)                                                                                       │      
   
app = FastAPI(title="API da LicitaAI")

@app.get("/")
def read_root():
    return {"message": "Olá, Mundo! Bem-vindo à API da LicitaAI."}
