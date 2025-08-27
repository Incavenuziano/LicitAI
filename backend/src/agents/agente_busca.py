import json
import httpx
import os
from datetime import datetime, timedelta

def consultar_licitacoes_publicadas(codigo_modalidade: int = 6) -> str:
    """
    Consulta licitações publicadas nos últimos 7 dias no PNCP, filtrando por modalidade.

    Args:
        codigo_modalidade (int, optional): O código da modalidade de contratação.
                                         Padrão: 6 (Pregão - Eletrônico).

    Returns:
        str: Uma string JSON contendo a lista de licitações encontradas ou uma mensagem de erro.
    """
    print(f"--- Executando busca de licitações (modalidade={codigo_modalidade}) ---")
    base_url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    
    data_inicial = "20250101"
    data_final = "20251231"
    
    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "codigoModalidadeContratacao": codigo_modalidade,
        "pagina": 1,
        "tamanhoPagina": 10
    }

    try:
        print(f"--- Enviando requisição para a API com os parâmetros: {params} ---")
        response = httpx.get(base_url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        
        print("--- Consulta à API PNCP bem-sucedida ---")
        
        if 'data' in data and data['data']:
            return json.dumps(data['data'], indent=2, ensure_ascii=False)
        else:
            return json.dumps({"mensagem": "Nenhuma licitação encontrada para os critérios fornecidos."}, indent=2)

    except httpx.HTTPStatusError as e:
        error_details = e.response.content.decode('utf-8', errors='replace')
        print(f"--- Erro na API PNCP: {e.response.status_code} - {error_details} ---")
        return json.dumps({"erro": "Falha ao consultar a API do PNCP.", "status_code": e.response.status_code, "detalhes": error_details})
    except Exception as e:
        print(f"--- Erro inesperado: {e} ---")
        return json.dumps({"erro": "Um erro inesperado ocorreu.", "detalhes": str(e)})

if __name__ == "__main__":
    print("Iniciando teste de busca de licitações...")
    print("-----------------------------------------")
    resultado_json = consultar_licitacoes_publicadas()
    print("\n--- Resultado da Consulta ---")
    # Tenta formatar o JSON para melhor leitura
    try:
        resultado_formatado = json.loads(resultado_json)
        print(json.dumps(resultado_formatado, indent=2, ensure_ascii=False))
    except json.JSONDecodeError:
        print(resultado_json)
