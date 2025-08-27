

import json
from sqlalchemy.orm import Session

# As importações agora são absolutas a partir da pasta 'backend' onde o comando será executado.
from src.agents.agente_busca import agente_busca
from src.agents.agente_tratamento import agente_tratamento
from src.database import engine, Base, get_db # Importa get_db
from src import models # Importa models para a verificação

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

    # 3. Extrair o resultado da ferramenta e acionar o Agente de Tratamento
    try:
        # Confirmado pela depuração: o resultado fica no atributo 'result'
        tool_result = resultado_busca_json.tools[0].result
        dados = json.loads(tool_result)

        if isinstance(dados, dict) and "erro" in dados:
            print(f"\nO Agente de Busca retornou uma mensagem de erro: {dados.get('detalhes', dados['erro'])}")
            print("Workflow interrompido.")
            return
        if not dados:
             print(f"\nO Agente de Busca não retornou dados.")
             print("Workflow concluído sem novas licitações.")
             return

    except (json.JSONDecodeError, AttributeError, IndexError) as e:
        print(f"\nFalha ao extrair ou decodificar o resultado do Agente de Busca.")
        print(f"Erro: {e}")
        print("Resposta completa do agente:", resultado_busca_json)
        print("Workflow interrompido.")
        return

    # Convertemos os dados para uma string JSON para passar ao próximo agente
    dados_para_tratamento = json.dumps(dados, indent=2, ensure_ascii=False)

    # Criamos um prompt explícito para o agente de tratamento
    prompt_tratamento = f"""Por favor, salve os seguintes dados de licitações no banco de dados usando sua ferramenta. Dados JSON: {dados_para_tratamento}"""

    print(f"\n[PASSO 2/2] Acionando o Agente de Tratamento para salvar os dados...")
    resultado_tratamento = agente_tratamento.run(prompt_tratamento)

    # 4. Imprimir o resultado final
    print("\n--- WORKFLOW CONCLUÍDO ---")
    print("Resultado final do Agente de Tratamento:")
    print(resultado_tratamento)

    # --- VERIFICAÇÃO IMEDIATA APÓS SALVAR ---
    try:
        print("\n--- Verificação imediata: Contando licitações no banco de dados ---")
        db_verify: Session = next(get_db())
        count_verify = db_verify.query(models.Licitacao).count()
        print(f">>> Verificação: Encontrado(s) {count_verify} registro(s) na tabela 'licitacoes'.")
        db_verify.close()
    except Exception as e:
        print(f"Erro durante a verificação imediata: {e}")
    # --- FIM DA VERIFICAÇÃO IMEDIATA ---

if __name__ == "__main__":
    executar_workflow()
