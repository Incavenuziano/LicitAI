
import json
import httpx
import os
from textwrap import dedent
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Importações do framework Agno
from agno.agent import Agent
from agno.models.google import Gemini

# Carrega as variáveis de ambiente do arquivo .env no diretório pai (backend/)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- Ferramenta de Consulta (Versão 2) ---

def consultar_licitacoes_publicadas(codigo_modalidade: int = 6) -> str:
    """
    Consulta licitações publicadas nos últimos 7 dias no PNCP, filtrando por modalidade.

    Args:
        codigo_modalidade (int, optional): O código da modalidade de contratação.
                                         Padrão: 6 (Pregão - Eletrônico).

    Returns:
        str: Uma string JSON contendo a lista de licitações encontradas ou uma mensagem de erro.
    """
    print(f"--- Executando ferramenta: consultar_licitacoes_publicadas(codigo_modalidade={codigo_modalidade}) ---")
    base_url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    
    # Define o período de busca para os últimos 7 dias
    data_final_dt = datetime.now()
    data_inicial_dt = data_final_dt - timedelta(days=7)
    
    data_final = data_final_dt.strftime('%Y%m%d')
    data_inicial = data_inicial_dt.strftime('%Y%m%d')
    
    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "codigoModalidadeContratacao": codigo_modalidade,
        "pagina": 1,
        "tamanhoPagina": 50
    }

    try:
        print(f"--- Enviando requisição para a API com os parâmetros: {params} ---")
        response = httpx.get(base_url, params=params, timeout=30.0)

        # Verifica se houve erro na requisição HTTP
        response.raise_for_status()

        # Força a decodificação correta para caracteres brasileiros ANTES de processar o JSON
        response.encoding = 'latin-1'
        data = response.json()
        
        print("--- Consulta à API PNCP bem-sucedida ---")
        
        if 'data' in data and data['data']:
            return json.dumps(data['data'], indent=2, ensure_ascii=False)
        else:
            return json.dumps({"mensagem": "Nenhuma licitação encontrada para os critérios fornecidos."}, indent=2)

    except httpx.HTTPStatusError as e:
        # Se a resposta for um erro, decodifica o corpo do erro da mesma forma
        error_details = e.response.content.decode('latin-1', errors='replace')
        print(f"--- Erro na API PNCP: {e.response.status_code} - {error_details} ---")
        return json.dumps({"erro": "Falha ao consultar a API do PNCP.", "status_code": e.response.status_code, "detalhes": error_details})
    except Exception as e:
        print(f"--- Erro inesperado: {e} ---")
        return json.dumps({"erro": "Um erro inesperado ocorreu.", "detalhes": str(e)})

# --- Definição do Agente (Versão 2) ---

agente_busca = Agent(
    model=Gemini(id="gemini-1.5-flash"),
    instructions=dedent("""
        Você é um assistente especialista em licitações públicas no Brasil.
        Sua função é encontrar licitações publicadas recentemente.
        Use a ferramenta `consultar_licitacoes_publicadas` para buscar.
        Por padrão, a ferramenta busca por Pregões Eletrônicos (código 6) publicados nos últimos 7 dias.
        Se o usuário pedir outra modalidade, você pode alterar o código.
        Apresente os resultados de forma clara e organizada.
    """
    ),
    tools=[consultar_licitacoes_publicadas],
    show_tool_calls=True,
    markdown=True,
)

# --- Exemplo de Uso (Versão 2) ---

if __name__ == "__main__":
    print("Iniciando o Agente de Busca de Licitações (v2)...")
    print("--------------------------------------------------")
    
    pergunta = "Encontre os pregões eletrônicos mais recentes."
    
    agente_busca.print_response(pergunta, stream=True)
