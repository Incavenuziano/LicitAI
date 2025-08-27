import sys
import traceback
from sqlalchemy.orm import Session
import crud
import schemas
from database import get_db

print("--- Iniciando teste de serialização ---")

db: Session = next(get_db())
item_id_com_erro = None
try:
    print("Buscando licitações do banco de dados...")
    licitacoes_from_db = crud.get_licitacoes(db, limit=100) # Pega todos os 10
    print(f"Encontradas {len(licitacoes_from_db)} licitações no banco.")
    if not licitacoes_from_db:
        print("Nenhuma licitação no banco para testar. Saindo.")
        sys.exit()

    print("\nIniciando o teste de validação/serialização do Pydantic...")
    # Este loop imita o que `response_model=List[schemas.Licitacao]` faz internamente.
    for item in licitacoes_from_db:
        item_id_com_erro = item.id # Guarda o ID para o caso de erro
        print(f"Testando item ID: {item.id}...")
        # Para Pydantic v2, model_validate é o método correto para validar um objeto ORM
        validated_item = schemas.Licitacao.model_validate(item)
    
    print("\n✅ SUCESSO! Todos os dados do banco são compatíveis com o schema Pydantic.")

except Exception as e:
    print(f"\n❌ ERRO ENCONTRADO NO ITEM ID: {item_id_com_erro}! Ocorreu uma falha durante a validação/serialização.")
    print("Este é o erro que estava travando o servidor silenciosamente:")
    traceback.print_exc()

finally:
    print("\n--- Teste de serialização concluído ---")
    db.close()
