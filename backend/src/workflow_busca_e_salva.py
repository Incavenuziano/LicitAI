
import json

# As importações agora são absolutas a partir da pasta 'backend' onde o comando será executado.
from src.agents.agente_busca import agente_busca
from src.agents.agente_tratamento import agente_tratamento
from src.database import engine, Base

def executar_workflow():
    """
    Orquestra a execução dos agentes de busca and tratamento.
    """
    print("--- INICIANDO WORKFLOW DE BUSCA E ARMAZENAMENTO DE LICITAÇÕES ---")

    # 1. Garantir que as tabelas do banco de dados estão criadas
    print("Verificando e criando tabelas do banco de dados, se necessário...")
    Base.metadata.create_all(bind=engine)
    print("Tabelas prontas.")

    # 2. Executar o Agente de Busca
    pergunta_busca = "Encontre os pregões eletrônicos mais recentes."
    print(f"\n[PASSO 1/2] Acionando o Agente de Busca com a pergunta: '{pergunta_busca}'")
    
    # Usamos .run() em vez de .print_response() para capturar a saída como uma string
    resultado_busca_json = agente_busca.run(pergunta_busca)
    
    print("Agente de Busca concluiu. Resultado recebido.")

    # 3. Verificar o resultado e acionar o Agente de Tratamento
    try:
        # Tenta carregar o JSON para verificar se é válido e não é uma mensagem de erro
        dados = json.loads(resultado_busca_json)
        if isinstance(dados, dict) and "erro" in dados:
            print(f"\nO Agente de Busca retornou um erro: {dados['erro']}")
            print("Workflow interrompido.")
            return
        if not dados:
             print(f"\nO Agente de Busca não retornou dados.")
             print("Workflow concluído sem novas licitações.")
             return

    except json.JSONDecodeError:
        print(f"\nO Agente de Busca retornou uma resposta que não é JSON: {resultado_busca_json}")
        print("Workflow interrompido.")
        return

    print(f"\n[PASSO 2/2] Acionando o Agente de Tratamento para salvar os dados...")
    resultado_tratamento = agente_tratamento.run(resultado_busca_json)

    # 4. Imprimir o resultado final
    print("\n--- WORKFLOW CONCLUÍDO ---")
    print("Resultado final do Agente de Tratamento:")
    print(resultado_tratamento)

if __name__ == "__main__":
    executar_workflow()
