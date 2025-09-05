# -*- coding: utf-8 -*-
from typing import Optional, List, Dict, Any
import httpx
import re

def comprasnet_buscar_por_termo(
    termo: str,
    *,
    data_inicio: Optional[str] = None, # YYYY-MM-DD
    data_fim: Optional[str] = None,    # YYYY-MM-DD
    codigo_modalidade: Optional[int] = None,
    timeout: float = 45.0,
) -> List[Dict[str, Any]]:
    """
    Busca licitações no Comprasnet (API de Dados Abertos) por um termo de busca.

    Endpoint: GET /modulo-legado/1_consultarLicitacao
    """
    base_url = "https://dadosabertos.compras.gov.br/modulo-legado/1_consultarLicitacao"
    
    params = {
        "descricao": termo,
        "format": "json"
    }
    if data_inicio:
        params["data_publicacao_inicio"] = data_inicio
    if data_fim:
        params["data_publicacao_fim"] = data_fim
    if codigo_modalidade:
        params["modalidade"] = codigo_modalidade

    try:
        print(f"--- Executando busca no Comprasnet com termo: '{termo}' ---")
        response = httpx.get(base_url, params=params, timeout=timeout)
        response.raise_for_status()
        
        data = response.json()
        
        # A API pode retornar os resultados dentro de uma chave, e.g., "_embedded" ou "licitacoes"
        # Inspecionando a estrutura comum dessas APIs
        if isinstance(data, dict):
            if "licitacoes" in data:
                return data["licitacoes"]
            if "_embedded" in data and "licitacoes" in data["_embedded"]:
                return data["_embedded"]["licitacoes"]
        
        # Se a resposta for uma lista diretamente
        if isinstance(data, list):
            return data

        return []

    except httpx.HTTPStatusError as e:
        print(f"--- Erro na API Comprasnet: {e.response.status_code} - {e.response.text} ---")
        return []
    except Exception as e:
        print(f"--- Erro inesperado na busca do Comprasnet: {e} ---")
        return []

if __name__ == '__main__':
    print("Iniciando teste de busca no Comprasnet...")
    termo_teste = "consultoria"
    resultados = comprasnet_buscar_por_termo(termo_teste)
    
    if resultados:
        print(f"Encontrados {len(resultados)} resultados para '{termo_teste}':")
        # Imprime o primeiro resultado como exemplo
        import json
        print(json.dumps(resultados[0], indent=2, ensure_ascii=False))
    else:
        print(f"Nenhum resultado encontrado para '{termo_teste}'.")


def cnpj_by_uasg(uasg: int, *, timeout: float = 30.0) -> Optional[str]:
    """Resolve o CNPJ de uma UASG via Dados Abertos do Compras.

    Endpoint: http://compras.dados.gov.br/licitacoes/id/uasg/{UASG}.json
    Retorna o CNPJ apenas com dígitos (14 chars) ou None.
    """
    try:
        url = f"http://compras.dados.gov.br/licitacoes/id/uasg/{int(uasg)}.json"
        r = httpx.get(url, timeout=timeout)
        r.raise_for_status()
        js = r.json()
        raw = js.get("cnpj") or js.get("CNPJ") or ""
        if not raw:
            return None
        cnpj = re.sub(r"\D+", "", str(raw))
        return cnpj if len(cnpj) == 14 else None
    except Exception:
        return None
