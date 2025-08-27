from sqlalchemy.orm import sessionmaker
from .database import engine
from .models import Licitacao

def verificar_dados():
    """
    Conecta ao banco de dados e conta o número de registros na tabela de licitações.
    """
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("--- Contando licitações no banco de dados ---")
        count = session.query(Licitacao).count()
        print(f"\n>>> Encontrado(s) {count} registro(s) na tabela 'licitacoes'.\n")

        if count > 0:
            print("Sucesso! O pipeline de dados está funcionando e salvando no banco.")
        else:
            print("A tabela 'licitacoes' está vazia. O workflow pode ter rodado em um período sem novas licitações.")

    except Exception as e:
        print(f"Ocorreu um erro ao acessar o banco de dados: {e}")
    finally:
        session.close()
        print("Conexão com o banco de dados fechada.")

if __name__ == "__main__":
    verificar_dados()
