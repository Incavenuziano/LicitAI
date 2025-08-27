import json

# Importa as funções diretamente, em vez dos objetos de agente
from .agents.agente_busca import consultar_licitacoes_publicadas
from .agents.agente_tratamento import salvar_licitacoes
from .agents.agente_analise import analisar_licitacoes_com_pandas

def executar_workflow_completo():
    """
    Orquestra o fluxo completo de busca, salvamento e análise de licitações.
    """
    print("--- INICIANDO WORKFLOW COMPLETO ---")

    # --- Etapa 1: Buscar novas licitações ---
    print("\n--- Etapa 1: Buscando novas licitações ---")
    licitacoes_json_str = consultar_licitacoes_publicadas()
    print("Busca concluída.")

    # --- Etapa 2: Salvar licitações no banco de dados ---
    try:
        # Tenta carregar o JSON para verificar se a busca retornou dados válidos
        licitacoes_encontradas = json.loads(licitacoes_json_str)
        
        # A API pode retornar um JSON com uma mensagem de erro ou lista vazia
        if isinstance(licitacoes_encontradas, dict) and ('erro' in licitacoes_encontradas or 'mensagem' in licitacoes_encontradas):
            print(f"Nenhuma licitação nova encontrada ou erro na API. Mensagem: {licitacoes_encontradas}")
        elif isinstance(licitacoes_encontradas, list) and licitacoes_encontradas:
            print(f"\n--- Etapa 2: {len(licitacoes_encontradas)} licitações encontradas. Salvando no banco de dados ---")
            salvar_licitacoes(licitacoes_json_str)
            print("Salvamento concluído.")
        else:
            print("Nenhuma licitação nova encontrada.")

    except (json.JSONDecodeError, TypeError):
        print(f"Erro: A busca não retornou um JSON válido. Resposta: {licitacoes_json_str}")
        # Mesmo com erro na busca, a análise dos dados existentes prosseguirá

    # --- Etapa 3: Gerar relatório de análise com Pandas ---
    print("\n--- Etapa 3: Gerando relatório de análise dos dados existentes ---")
    relatorio_analise = analisar_licitacoes_com_pandas()
    print(relatorio_analise)

    print("\n--- WORKFLOW COMPLETO FINALIZADO ---")

if __name__ == "__main__":
    executar_workflow_completo()
